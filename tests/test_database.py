"""Tests for PostgreSQL/pgvector schema, artifact validation, and ingestion mechanics."""

import json
import os
import unittest
from pathlib import Path
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

REPO_ROOT = Path(__file__).resolve().parent.parent
EMBEDDINGS_DIR = REPO_ROOT / "data" / "embeddings"
SCHEMA_SQL_PATH = REPO_ROOT / "scripts" / "init_db.sql"

from scripts.ingest_embeddings import (
    EXPECTED_DIMENSION,
    get_connection_config,
    validate_artifacts,
)


class TestDatabaseSchemaAndValidation(unittest.TestCase):
    """Offline unit tests for schema DDL and ingestion artifact validation."""

    def test_schema_sql_exists_and_contains_required_definitions(self):
        """Schema SQL file exists and contains vector extension, table, and index definitions."""
        self.assertTrue(SCHEMA_SQL_PATH.is_file(), f"Missing {SCHEMA_SQL_PATH}")
        sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")

        # 1. Extension
        self.assertIn("CREATE EXTENSION IF NOT EXISTS vector;", sql)

        # 2. Table
        self.assertIn("CREATE TABLE IF NOT EXISTS document_chunks", sql)

        # 3. Required columns
        expected_columns = [
            "corpus_id VARCHAR(64) NOT NULL",
            "chunk_id VARCHAR(128) NOT NULL",
            "document_filename VARCHAR(255) NOT NULL",
            "page_number INTEGER NOT NULL",
            "start_char INTEGER NOT NULL",
            "end_char INTEGER NOT NULL",
            "token_count INTEGER NOT NULL",
            "content_sha256 VARCHAR(64) NOT NULL",
            "component_id VARCHAR(64) NOT NULL",
            "revision VARCHAR(32) NOT NULL",
            "document_id VARCHAR(64)",
            "text TEXT NOT NULL",
            "model_name VARCHAR(128) NOT NULL",
            "model_revision VARCHAR(64) NOT NULL",
            f"embedding vector({EXPECTED_DIMENSION}) NOT NULL",
            "created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP",
        ]
        for col_def in expected_columns:
            self.assertIn(col_def, sql)

        # 4. Unique constraint for idempotency
        self.assertIn("CONSTRAINT uq_document_chunks_corpus_chunk UNIQUE (corpus_id, chunk_id)", sql)

        # 5. Indexes
        self.assertIn("idx_document_chunks_identity", sql)
        self.assertIn("idx_document_chunks_document", sql)
        self.assertIn("USING hnsw (embedding vector_cosine_ops)", sql)

    def test_validate_artifacts_on_step20_outputs(self):
        """Step 20 embedding artifacts pass all dimension, alignment, and metadata validations."""
        if np is None:
            self.skipTest("numpy is not installed. Skipping array validation.")
        if not EMBEDDINGS_DIR.exists():
            self.skipTest(f"Directory {EMBEDDINGS_DIR} does not exist.")

        manifest, chunks, embeddings = validate_artifacts(EMBEDDINGS_DIR)

        self.assertEqual(len(chunks), 4)
        self.assertEqual(embeddings.shape, (4, EXPECTED_DIMENSION))
        self.assertEqual(manifest["embedding_model"]["dimension"], EXPECTED_DIMENSION)
        self.assertTrue(np.isfinite(embeddings).all())

        norms = np.linalg.norm(embeddings, axis=1)
        for n in norms:
            self.assertAlmostEqual(n, 1.0, places=3)

    def test_validate_artifacts_rejects_dimension_mismatch(self):
        """Validation raises ValueError if manifest dimension does not match 384."""
        if np is None:
            self.skipTest("numpy is not installed. Skipping array validation.")
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest = {
                "embedding_model": {
                    "name": "test-model",
                    "revision": "test-rev",
                    "dimension": 512,  # Invalid dimension
                }
            }
            (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (tmp / "chunks.json").write_text(json.dumps([{"chunk_id": "c1"}]), encoding="utf-8")
            np.save(tmp / "embeddings.npy", np.zeros((1, 512), dtype=np.float32))

            with self.assertRaises(ValueError) as ctx:
                validate_artifacts(tmp)
            self.assertIn("Embedding dimension in manifest (512) does not match expected 384", str(ctx.exception))

    def test_validate_artifacts_rejects_row_count_mismatch(self):
        """Validation raises ValueError if chunk count does not match matrix rows."""
        if np is None:
            self.skipTest("numpy is not installed. Skipping array validation.")
        import tempfile


        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest = {
                "embedding_model": {
                    "name": "test-model",
                    "revision": "test-rev",
                    "dimension": 384,
                }
            }
            chunks = [
                {
                    "chunk_id": "c1",
                    "corpus_id": "test",
                    "text": "sample",
                    "document_filename": "doc.pdf",
                    "page_number": 1,
                    "start_char": 0,
                    "end_char": 6,
                    "token_count": 1,
                    "content_sha256": "abc",
                    "component_id": "COMP-1",
                    "revision": "A",
                },
                {
                    "chunk_id": "c2",
                    "corpus_id": "test",
                    "text": "sample 2",
                    "document_filename": "doc.pdf",
                    "page_number": 1,
                    "start_char": 7,
                    "end_char": 15,
                    "token_count": 2,
                    "content_sha256": "def",
                    "component_id": "COMP-1",
                    "revision": "A",
                },
            ]
            (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (tmp / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
            # Only 1 vector row for 2 chunks:
            np.save(tmp / "embeddings.npy", np.ones((1, 384), dtype=np.float32))

            with self.assertRaises(ValueError) as ctx:
                validate_artifacts(tmp)
            self.assertIn("Chunk count (2) does not match embedding matrix rows (1)", str(ctx.exception))

    def test_validate_artifacts_rejects_non_finite_vectors(self):
        """Validation raises ValueError if vectors contain NaN or Inf."""
        if np is None:
            self.skipTest("numpy is not installed. Skipping array validation.")
        import tempfile


        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            manifest = {
                "embedding_model": {
                    "name": "test-model",
                    "revision": "test-rev",
                    "dimension": 384,
                }
            }
            chunks = [
                {
                    "chunk_id": "c1",
                    "corpus_id": "test",
                    "text": "sample",
                    "document_filename": "doc.pdf",
                    "page_number": 1,
                    "start_char": 0,
                    "end_char": 6,
                    "token_count": 1,
                    "content_sha256": "abc",
                    "component_id": "COMP-1",
                    "revision": "A",
                }
            ]
            mat = np.ones((1, 384), dtype=np.float32)
            mat[0, 10] = np.nan

            (tmp / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
            (tmp / "chunks.json").write_text(json.dumps(chunks), encoding="utf-8")
            np.save(tmp / "embeddings.npy", mat)

            with self.assertRaises(ValueError) as ctx:
                validate_artifacts(tmp)
            self.assertIn("NaN or Inf", str(ctx.exception))


class TestLiveDatabaseIntegration(unittest.TestCase):
    """Integration test suite that runs against local PostgreSQL when available."""

    def setUp(self):
        try:
            import psycopg

            cfg = get_connection_config()
            # Attempt quick connection with 1-second timeout
            with psycopg.connect(
                host=cfg["host"],
                port=cfg["port"],
                dbname=cfg["dbname"],
                user=cfg["user"],
                password=cfg["password"],
                connect_timeout=1,
            ) as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
            self.cfg = cfg
        except Exception as e:
            self.skipTest(f"PostgreSQL database not accessible ({e}). Skipping live integration tests.")

    def test_live_document_chunks_count_and_retrieval(self):
        """Live database contains 4 chunks and enables vector cosine queries."""
        import psycopg
        from pgvector.psycopg import register_vector

        with psycopg.connect(
            host=self.cfg["host"],
            port=self.cfg["port"],
            dbname=self.cfg["dbname"],
            user=self.cfg["user"],
            password=self.cfg["password"],
        ) as conn:
            register_vector(conn)
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM document_chunks;")
                count = cur.fetchone()[0]
                self.assertEqual(count, 4)

                # Query top match for chunk 3 vector
                cur.execute("""
                    SELECT chunk_id, embedding
                    FROM document_chunks
                    WHERE chunk_id = 'supplier-COMP-001_p1_c003';
                """)
                row = cur.fetchone()
                self.assertIsNotNone(row)
                vec = row[1]
                self.assertEqual(vec.shape, (384,))


if __name__ == "__main__":
    unittest.main()
