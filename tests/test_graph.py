"""Unit and integration tests for LangGraph StateGraph investigation workflow."""

import json
import os
import unittest
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import MagicMock, patch

REPO_ROOT = Path(__file__).resolve().parent.parent

from scripts.extractors import BaseMeasurementExtractor, ExtractorResult
from scripts.investigate_record import investigate_record

try:
    import langgraph
    from scripts.investigate_graph import (
        LANGGRAPH_AVAILABLE,
        get_compiled_graph,
        investigate_record_langgraph,
    )
except ImportError:
    LANGGRAPH_AVAILABLE = False


class FakeGeminiMockExtractor(BaseMeasurementExtractor):
    """Mock Gemini extractor returning configurable extraction results for offline testing."""

    def __init__(
        self,
        status: str = "found",
        val: Optional[Decimal] = Decimal("0.8"),
        unit: Optional[str] = "cm",
        attr: Optional[str] = "thickness",
        quote: Optional[str] = "Component thickness: 0.8 cm.",
        err: Optional[str] = None,
        err_type: Optional[str] = None,
    ):
        self._status = status
        self._val = val
        self._unit = unit
        self._attr = attr
        self._quote = quote
        self._err = err
        self._err_type = err_type

    @property
    def provider(self) -> str:
        return "google-genai"

    @property
    def model(self) -> str:
        return "mock-gemini-2.5-flash"

    def extract_measurement(self, evidence_passage: str, attribute_name: str) -> ExtractorResult:
        return ExtractorResult(
            status=self._status,
            value=self._val,
            unit=self._unit,
            measurement_name=self._attr,
            quote=self._quote,
            error_message=self._err,
            error_type=self._err_type,
            provider=self.provider,
            model=self.model,
            is_fallback=False,
            call_duration_ms=15.0,
            token_usage={"prompt_tokens": 120, "candidates_tokens": 25, "total_tokens": 145},
        )


class TestLangGraphStructureAndTransitions(unittest.TestCase):
    """Unit tests for LangGraph StateGraph structure, guarded edges, and telemetry."""

    def setUp(self):
        if not LANGGRAPH_AVAILABLE:
            self.skipTest("langgraph is not installed. Skipping LangGraph tests.")

    def test_graph_has_six_explicit_nodes(self):
        """Graph contains all 6 explicit nodes and compiles successfully."""
        graph = get_compiled_graph()
        self.assertIsNotNone(graph)
        expected_nodes = {
            "validate_record",
            "retrieve_evidence",
            "extract_measurement",
            "validate_evidence",
            "convert_and_compare",
            "finalize",
        }
        # In LangGraph compiled graphs, nodes are inspectable via graph.nodes
        for node in expected_nodes:
            self.assertIn(node, graph.nodes, f"Missing node '{node}' in StateGraph")

    def test_route_eligible_case_executes_all_six_nodes(self):
        """Eligible evidence case (case-01) visits all 6 nodes in strict order."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

        res, tel = investigate_record_langgraph(rec_path, extracted_dir=ext_dir, return_telemetry=True)

        expected_transitions = [
            "validate_record",
            "retrieve_evidence",
            "extract_measurement",
            "validate_evidence",
            "convert_and_compare",
            "finalize",
        ]
        self.assertEqual(tel["node_transitions"], expected_transitions)
        self.assertEqual(res["outcome"], "correction_proposed")
        self.assertEqual(tel["tool_invocations"].get("evidence_retrieval_tool"), 1)
        self.assertEqual(tel["tool_invocations"].get("measurement_extraction_tool"), 1)
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool"), 1)
        self.assertEqual(tel["extractor_invocations"], 1)

    def test_route_invalid_record_short_circuits_to_finalize(self):
        """Invalid record (case-10) routes validate_record -> finalize directly."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-10-malformed-measurement" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-10-malformed-measurement" / "extracted"

        res, tel = investigate_record_langgraph(rec_path, extracted_dir=ext_dir, return_telemetry=True)

        expected_transitions = ["validate_record", "finalize"]
        self.assertEqual(tel["node_transitions"], expected_transitions)
        self.assertEqual(res["outcome"], "needs_review")
        self.assertEqual(tel["tool_invocations"].get("evidence_retrieval_tool", 0), 0)
        self.assertEqual(tel["tool_invocations"].get("measurement_extraction_tool", 0), 0)
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool", 0), 0)
        self.assertEqual(tel["extractor_invocations"], 0)

    def test_route_missing_evidence_short_circuits_to_finalize(self):
        """Unknown component (case-05) routes validate_record -> retrieve_evidence -> finalize."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "extracted"

        res, tel = investigate_record_langgraph(rec_path, extracted_dir=ext_dir, return_telemetry=True)

        expected_transitions = ["validate_record", "retrieve_evidence", "finalize"]
        self.assertEqual(tel["node_transitions"], expected_transitions)
        self.assertEqual(res["outcome"], "insufficient_evidence")
        self.assertEqual(tel["tool_invocations"].get("evidence_retrieval_tool"), 1)
        self.assertEqual(tel["tool_invocations"].get("measurement_extraction_tool", 0), 0)
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool", 0), 0)
        self.assertEqual(tel["extractor_invocations"], 0)
        self.assertEqual(res["extractor"]["status"], "not_invoked")

    def test_route_conflicting_evidence_short_circuits_to_finalize(self):
        """Conflicting evidence (case-08) routes validate_record -> retrieve_evidence -> finalize."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "extracted"

        res, tel = investigate_record_langgraph(rec_path, extracted_dir=ext_dir, return_telemetry=True)

        expected_transitions = ["validate_record", "retrieve_evidence", "finalize"]
        self.assertEqual(tel["node_transitions"], expected_transitions)
        self.assertEqual(res["outcome"], "ambiguous_evidence")
        self.assertEqual(tel["tool_invocations"].get("evidence_retrieval_tool"), 1)
        self.assertEqual(tel["tool_invocations"].get("measurement_extraction_tool", 0), 0)
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool", 0), 0)
        self.assertEqual(tel["extractor_invocations"], 0)
        self.assertEqual(res["extractor"]["status"], "not_invoked")

    def test_route_unsupported_unit_short_circuits_before_conversion(self):
        """Unsupported unit in evidence (case-09) stops at validate_evidence without calling conversion."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-09-unsupported-unit" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-09-unsupported-unit" / "extracted"

        res, tel = investigate_record_langgraph(rec_path, extracted_dir=ext_dir, return_telemetry=True)

        expected_transitions = [
            "validate_record",
            "retrieve_evidence",
            "extract_measurement",
            "validate_evidence",
            "finalize",
        ]
        self.assertEqual(tel["node_transitions"], expected_transitions)
        self.assertEqual(res["outcome"], "needs_review")
        self.assertEqual(tel["tool_invocations"].get("evidence_retrieval_tool"), 1)
        self.assertEqual(tel["tool_invocations"].get("measurement_extraction_tool"), 1)
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool", 0), 0)
        self.assertIsNone(res["proposed_correction"])


class TestLangGraphGuardrailsAndGrounding(unittest.TestCase):
    """Unit tests for model grounding, whitespace alignment, and guardrails via LangGraph."""

    def setUp(self):
        if not LANGGRAPH_AVAILABLE:
            self.skipTest("langgraph is not installed. Skipping LangGraph tests.")
        self.rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        self.ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

    def test_whitespace_aware_quote_alignment_through_graph(self):
        """Whitespace variations in model quote align successfully to verbatim passage span."""
        mock = FakeGeminiMockExtractor(quote="Component   thickness:   0.8   cm.")
        res, tel = investigate_record_langgraph(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            return_telemetry=True,
        )
        self.assertEqual(res["outcome"], "correction_proposed")
        self.assertEqual(res["proposed_correction"]["value"], 8.0)
        self.assertEqual(res["evidence"]["quote_alignment"], "whitespace_aligned")
        self.assertEqual(res["evidence"]["supporting_passage"], "Component thickness: 0.8 cm.")
        self.assertEqual(res["evidence"]["model_quote"], "Component   thickness:   0.8   cm.")
        self.assertIn("convert_and_compare", tel["node_transitions"])

    def test_ungrounded_quote_fails_guardrail_and_yields_needs_review(self):
        """Hallucinated or ungrounded model quote triggers guardrail failure without proposing correction."""
        mock = FakeGeminiMockExtractor(quote="Fabricated ungrounded quote 15.0 mm")
        res, tel = investigate_record_langgraph(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            return_telemetry=True,
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertIn("Ungrounded extraction", res["explanation"])
        self.assertNotIn("convert_and_compare", tel["node_transitions"])
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool", 0), 0)

    def test_mismatched_attribute_fails_guardrail(self):
        """Extractor returning wrong attribute triggers guardrail failure without proposing correction."""
        mock = FakeGeminiMockExtractor(attr="width")
        res, tel = investigate_record_langgraph(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            return_telemetry=True,
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertIn("Mismatched measurement", res["explanation"])
        self.assertNotIn("convert_and_compare", tel["node_transitions"])

    def test_extraction_error_routes_to_finalize_without_guardrails_or_conversion(self):
        """Extraction error routes directly to finalize."""
        mock = FakeGeminiMockExtractor(status="error", err="Safety blocked output", err_type="PROVIDER_ERROR")
        res, tel = investigate_record_langgraph(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            return_telemetry=True,
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertEqual(
            tel["node_transitions"],
            ["validate_record", "retrieve_evidence", "extract_measurement", "finalize"],
        )
        self.assertEqual(tel["tool_invocations"].get("measurement_conversion_tool", 0), 0)


class TestLangGraphStateIsolation(unittest.TestCase):
    """Test state isolation, immutability, and confidentiality in LangGraph execution."""

    def setUp(self):
        if not LANGGRAPH_AVAILABLE:
            self.skipTest("langgraph is not installed. Skipping LangGraph tests.")

    def test_state_isolation_across_consecutive_runs(self):
        """Consecutive runs with different records cannot cross-contaminate state."""
        rec1_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext1_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"
        rec5_path = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "record.json"
        ext5_dir = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "extracted"

        res1, tel1 = investigate_record_langgraph(rec1_path, extracted_dir=ext1_dir, return_telemetry=True)
        res5, tel5 = investigate_record_langgraph(rec5_path, extracted_dir=ext5_dir, return_telemetry=True)
        res1_second, tel1_second = investigate_record_langgraph(rec1_path, extracted_dir=ext1_dir, return_telemetry=True)

        self.assertEqual(res1["case_id"], "case-01-correction-cm-to-mm")
        self.assertEqual(res5["case_id"], "case-05-unknown-component")
        self.assertEqual(res1_second["case_id"], "case-01-correction-cm-to-mm")

        # Telemetry counts are fresh per invocation
        self.assertEqual(tel1["tool_invocations"], tel1_second["tool_invocations"])
        self.assertNotEqual(tel1["node_transitions"], tel5["node_transitions"])

    def test_credentials_and_expected_answers_excluded_from_state(self):
        """Input record containing expected answers or credentials does not propagate to graph state."""
        rec = {
            "case_id": "test-security-case",
            "record_id": "SEC-001",
            "component_id": "COMP-001",
            "revision": "A",
            "attribute_name": "thickness",
            "recorded_value": 0.8,
            "recorded_unit": "mm",
            "expected_outcome": "CORRECTION_LEAK",
            "expected_correction": {"value": 8.0, "unit": "mm"},
            "gemini_api_key": "SECRET_LEAK_KEY",
        }
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

        res = investigate_record(rec, extracted_dir=ext_dir, orchestration="langgraph")

        # Verify output does not leak ungrounded expected answers or credentials
        res_str = json.dumps(res)
        self.assertNotIn("SECRET_LEAK_KEY", res_str)
        self.assertNotIn("CORRECTION_LEAK", res_str)
        self.assertEqual(res["outcome"], "correction_proposed")


class TestLangGraphDependencyIsolation(unittest.TestCase):
    """Verify direct and langchain execution work independently when langgraph is absent."""

    def test_direct_execution_independent_of_langgraph(self):
        """Direct execution succeeds when langgraph is not used."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

        res = investigate_record(rec_path, extracted_dir=ext_dir, orchestration="direct")
        self.assertEqual(res["outcome"], "correction_proposed")
        self.assertEqual(res["proposed_correction"]["value"], 8.0)

    def test_langgraph_opt_in_raises_helpful_error_when_missing(self):
        """Opting into langgraph when module is missing raises clear ImportError."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

        with patch.dict("sys.modules", {"langgraph": None, "scripts.investigate_graph": None}):
            with self.assertRaises((ImportError, ModuleNotFoundError)):
                investigate_record(rec_path, extracted_dir=ext_dir, orchestration="langgraph")


class TestLangGraphLivePgVectorIntegration(unittest.TestCase):
    """Integration test confirming live pgvector retrieval matches direct execution."""

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
        if not LANGGRAPH_AVAILABLE:
            self.skipTest("langgraph is not installed.")
        if not getattr(self, "db_available", False):
            self.skipTest("PostgreSQL/pgvector database is not available on localhost:5432.")

    def test_live_pgvector_retrieval_parity(self):
        """Live pgvector retrieval through LangGraph matches direct and LangChain execution."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        res_direct = investigate_record(
            rec_path,
            retriever="pgvector",
            corpus_id="eval-case-01-correction-cm-to-mm",
            orchestration="direct",
        )
        res_chain = investigate_record(
            rec_path,
            retriever="pgvector",
            corpus_id="eval-case-01-correction-cm-to-mm",
            orchestration="langchain",
        )
        res_graph = investigate_record(
            rec_path,
            retriever="pgvector",
            corpus_id="eval-case-01-correction-cm-to-mm",
            orchestration="langgraph",
        )

        self.assertEqual(res_direct["outcome"], res_graph["outcome"])
        self.assertEqual(res_direct["proposed_correction"], res_graph["proposed_correction"])
        self.assertEqual(res_chain["proposed_correction"], res_graph["proposed_correction"])
        self.assertEqual(res_graph["evidence"]["document_filename"], "supplier-COMP-001.pdf")
        self.assertEqual(res_graph["evidence"]["context_type"], "chunk")


if __name__ == "__main__":
    unittest.main()
