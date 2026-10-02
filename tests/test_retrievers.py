"""Unit and integration tests for pluggable retrievers (Baseline & PgVector)."""

import json
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.retrievers import (
    DEFAULT_CORPUS_ID,
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    EXPECTED_DIMENSION,
    BaseRetriever,
    BaselineRetriever,
    PgVectorRetriever,
    get_retriever,
)


class TestRetrieverFactoryAndContract(unittest.TestCase):
    """Unit tests for retriever factory and interface contract."""

    def test_factory_resolves_baseline(self):
        """get_retriever('baseline') returns BaselineRetriever instance."""
        r = get_retriever("baseline")
        self.assertIsInstance(r, BaselineRetriever)
        self.assertEqual(r.name, "baseline")

        # Case-insensitivity and aliases
        self.assertIsInstance(get_retriever("BASELINE"), BaselineRetriever)
        self.assertIsInstance(get_retriever("deterministic"), BaselineRetriever)

    def test_factory_resolves_pgvector(self):
        """get_retriever('pgvector') returns PgVectorRetriever instance."""
        r = get_retriever("pgvector")
        self.assertIsInstance(r, PgVectorRetriever)
        self.assertEqual(r.name, "pgvector")
        self.assertEqual(r.model_name, DEFAULT_MODEL_NAME)
        self.assertEqual(r.model_revision, DEFAULT_MODEL_REVISION)

    def test_factory_rejects_unknown(self):
        """get_retriever with unknown retriever name raises ValueError."""
        with self.assertRaises(ValueError) as ctx:
            get_retriever("unknown_retriever")
        self.assertIn("Unknown retriever", str(ctx.exception))


class TestQueryFormulationAndFiltering(unittest.TestCase):
    """Unit tests for semantic query construction and metadata filtering."""

    def setUp(self):
        self.retriever = PgVectorRetriever()

    def test_query_text_construction_identity_only(self):
        """Query text uses only component ID and attribute name; never answers or values."""
        query = self.retriever.build_query_text("COMP-001", "thickness")
        self.assertEqual(query, "Component COMP-001 thickness physical dimension parameter specification")
        self.assertNotIn("0.8", query)
        self.assertNotIn("8.0", query)
        self.assertNotIn("mm", query)

    def test_retrieve_missing_component_or_attribute_abstains(self):
        """Record lacking component ID or attribute name immediately abstains with insufficient_evidence."""
        res_no_comp = self.retriever.retrieve({"attribute_name": "thickness"})
        self.assertEqual(res_no_comp["status"], "insufficient_evidence")

        res_no_attr = self.retriever.retrieve({"component_id": "COMP-001"})
        self.assertEqual(res_no_attr["status"], "insufficient_evidence")


def make_dummy_vector(dimension: int = EXPECTED_DIMENSION):
    """Create a dummy vector with .shape without requiring numpy in CI."""
    try:
        import numpy as np
        return np.zeros(dimension, dtype=np.float32)
    except ImportError:
        class DummyVector(list):
            @property
            def shape(self):
                return (dimension,)
        return DummyVector([0.0] * dimension)


class TestPgVectorMockedLogic(unittest.TestCase):
    """Offline unit tests with mocked database connection and embedding model."""

    def setUp(self):
        """Mock psycopg and pgvector drivers in sys.modules so offline CI runs without db drivers."""
        self.mock_psycopg = MagicMock()
        self.mock_pgvector = MagicMock()
        self.mock_pgvector_psycopg = MagicMock()
        self.patcher = patch.dict(
            "sys.modules",
            {
                "psycopg": self.mock_psycopg,
                "pgvector": self.mock_pgvector,
                "pgvector.psycopg": self.mock_pgvector_psycopg,
            },
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_missing_driver_returns_configuration_error(self):
        """When psycopg or pgvector is not installed, retriever gracefully returns CONFIGURATION_ERROR."""
        with patch.dict("sys.modules", {"psycopg": None, "pgvector": None, "pgvector.psycopg": None}):
            retriever = PgVectorRetriever()
            record = {
                "record_id": "REC-001",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
            }
            res = retriever.retrieve(record)
            self.assertEqual(res["status"], "error")
            self.assertEqual(res["retriever"]["error_type"], "CONFIGURATION_ERROR")
            self.assertIn("not installed", res["retriever"]["error_message"])

    def test_conflict_detection_across_full_context_before_ranking(self):
        """PgVectorRetriever detects contradictory specifications across full eligible context."""
        mock_model = MagicMock()
        mock_model.encode.return_value = make_dummy_vector()

        # Mock database connection returning two chunks with conflicting direct specs:
        # Chunk 1 (lower distance, ranks #1): thickness 0.8 cm
        # Chunk 2 (higher distance, ranks #2): thickness 1.2 cm
        mock_cursor = MagicMock()
        mock_cursor.fetchone.return_value = (True,)  # table exists
        mock_cursor.fetchall.return_value = [
            ("chunk_1", "doc.pdf", 1, 0, 100, 20, "sha1", "COMP-001", "A", "DOC-1",
             "2. Specifications\nComponent thickness: 0.8 cm.", 0.2),
            ("chunk_2", "doc.pdf", 1, 101, 200, 20, "sha2", "COMP-001", "A", "DOC-1",
             "2. Alternative\nComponent thickness: 1.2 cm.", 0.4),
        ]

        mock_conn = MagicMock()
        mock_conn.__enter__.return_value = mock_conn
        mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

        retriever = PgVectorRetriever(
            embedding_model_instance=mock_model,
            db_connection_factory=lambda: mock_conn,
        )

        record = {
            "record_id": "REC-001",
            "component_id": "COMP-001",
            "revision": "A",
            "attribute_name": "thickness",
            "recorded_value": 8.0,
            "recorded_unit": "mm",
        }

        res = retriever.retrieve(record)
        self.assertEqual(res["status"], "ambiguous_evidence")
        self.assertIn("Conflicting measurement values found", res["reason"])
        self.assertIn("0.8 cm", res["reason"])
        self.assertIn("1.2 cm", res["reason"])

    def test_database_password_sanitized_on_connection_error(self):
        """Database connection error strings mask passwords to prevent secret leakage."""
        mock_model = MagicMock()
        mock_model.encode.return_value = make_dummy_vector()

        def failing_connection():
            raise RuntimeError("connection to host localhost failed: password=super_secret_pw123 authentication failed")

        retriever = PgVectorRetriever(
            embedding_model_instance=mock_model,
            db_connection_factory=failing_connection,
        )

        record = {
            "record_id": "REC-001",
            "component_id": "COMP-001",
            "revision": "A",
            "attribute_name": "thickness",
        }

        res = retriever.retrieve(record)
        self.assertEqual(res["status"], "error")
        self.assertEqual(res["retriever"]["error_type"], "DATABASE_ERROR")
        err_msg = res["retriever"]["error_message"]
        self.assertNotIn("super_secret_pw123", err_msg)
        self.assertIn("password=***", err_msg)


class TestApiRetrieverIntegration(unittest.TestCase):
    """Offline API tests for retriever query parameter, payload field, and error responses."""

    def setUp(self):
        from fastapi.testclient import TestClient
        from api.main import app
        self.client = TestClient(app)
        self.sample_payload = {
            "record_id": "unit-mismatch-001",
            "component_id": "COMP-001",
            "revision": "A",
            "attribute_name": "thickness",
            "recorded_value": 0.8,
            "recorded_unit": "mm",
        }

    def test_api_accepts_retriever_query_param(self):
        """POST /investigations?retriever=baseline succeeds with status 200."""
        resp = self.client.post("/investigations?retriever=baseline", json=self.sample_payload)
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["outcome"], "correction_proposed")

    def test_api_rejects_invalid_retriever_422(self):
        """POST /investigations with invalid retriever returns HTTP 422 INVALID_RETRIEVER."""
        resp = self.client.post("/investigations?retriever=elasticsearch", json=self.sample_payload)
        self.assertEqual(resp.status_code, 422)
        data = resp.json()
        self.assertEqual(data["error_code"], "INVALID_RETRIEVER")
        self.assertIn("elasticsearch", data["detail"])

    def test_api_maps_retriever_config_error_to_503(self):
        """Retriever CONFIGURATION_ERROR maps to HTTP 503 RETRIEVER_NOT_CONFIGURED."""
        from api.main import app, get_retriever_dependency

        class MockConfigErrorRetriever(BaseRetriever):
            @property
            def name(self):
                return "pgvector"
            def retrieve(self, record, **kwargs):
                return {
                    "status": "error",
                    "retriever": {
                        "name": "pgvector",
                        "status": "error",
                        "error_type": "CONFIGURATION_ERROR",
                    },
                    "reason": "Missing pgvector driver",
                }

        app.dependency_overrides[get_retriever_dependency] = MockConfigErrorRetriever
        try:
            resp = self.client.post("/investigations?retriever=pgvector", json=self.sample_payload)
            self.assertEqual(resp.status_code, 503)
            data = resp.json()
            self.assertEqual(data["error_code"], "RETRIEVER_NOT_CONFIGURED")
        finally:
            app.dependency_overrides.clear()

    def test_api_maps_retriever_database_error_to_502(self):
        """Retriever DATABASE_ERROR maps to HTTP 502 RETRIEVER_SERVICE_ERROR."""
        from api.main import app, get_retriever_dependency

        class MockDbErrorRetriever(BaseRetriever):
            @property
            def name(self):
                return "pgvector"
            def retrieve(self, record, **kwargs):
                return {
                    "status": "error",
                    "retriever": {
                        "name": "pgvector",
                        "status": "error",
                        "error_type": "DATABASE_ERROR",
                    },
                    "reason": "Database connection timed out",
                }

        app.dependency_overrides[get_retriever_dependency] = MockDbErrorRetriever
        try:
            resp = self.client.post("/investigations?retriever=pgvector", json=self.sample_payload)
            self.assertEqual(resp.status_code, 502)
            data = resp.json()
            self.assertEqual(data["error_code"], "RETRIEVER_SERVICE_ERROR")
        finally:
            app.dependency_overrides.clear()


class TestLivePgVectorIntegration(unittest.TestCase):
    """Live database integration tests (executed when PostgreSQL is accessible)."""

    @classmethod
    def setUpClass(cls):
        try:
            import psycopg
            from scripts.ingest_embeddings import get_connection_config
            cfg = get_connection_config()
            with psycopg.connect(
                host=cfg["host"],
                port=cfg["port"],
                dbname=cfg["dbname"],
                user=cfg["user"],
                password=cfg["password"],
                connect_timeout=2,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM document_chunks;")
                    cls.chunk_count = cur.fetchone()[0]
            cls.db_available = True
        except Exception:
            cls.db_available = False

    def setUp(self):
        if not getattr(self, "db_available", False):
            self.skipTest("PostgreSQL/pgvector database is not available on localhost:5432.")

    def test_live_pgvector_retrieval_on_case_01(self):
        """Live pgvector retrieval on case-01 returns exact chunk and proposed correction."""
        from scripts.investigate_record import investigate_record
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        res = investigate_record(
            rec_path,
            retriever="pgvector",
            corpus_id="eval-case-01-correction-cm-to-mm",
        )
        self.assertEqual(res["outcome"], "correction_proposed")
        self.assertEqual(res["proposed_correction"]["value"], 8.0)
        self.assertEqual(res["proposed_correction"]["unit"], "mm")
        self.assertEqual(res["evidence"]["document_filename"], "supplier-COMP-001.pdf")
        self.assertEqual(res["evidence"]["page_number"], 1)
        self.assertEqual(res["evidence"]["context_type"], "chunk")
        self.assertGreater(res["evidence"]["similarity_score"], 0.70)

    def test_live_pgvector_conflict_detection_on_case_08(self):
        """Live pgvector retrieval on case-08 safely detects conflicting measurements."""
        from scripts.investigate_record import investigate_record
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "record.json"
        res = investigate_record(
            rec_path,
            retriever="pgvector",
            corpus_id="eval-case-08-conflicting-evidence",
        )
        self.assertEqual(res["outcome"], "ambiguous_evidence")
        self.assertIn("0.8 cm", res["explanation"])
        self.assertIn("1.2 cm", res["explanation"])


if __name__ == "__main__":
    unittest.main()
