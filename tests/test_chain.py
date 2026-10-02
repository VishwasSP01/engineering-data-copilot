"""Unit and integration tests for LangChain Runnable investigation workflow."""

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
    import langchain_core
    from langchain_core.documents import Document
    from scripts.investigate_chain import (
        create_investigation_workflow,
        investigate_record_langchain,
    )
    LANGCHAIN_INSTALLED = True
except ImportError:
    LANGCHAIN_INSTALLED = False


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


class TestLangChainWorkflowComposition(unittest.TestCase):
    """Unit tests for LangChain Runnable pipeline composition, stage naming, and state."""

    def setUp(self):
        if not LANGCHAIN_INSTALLED:
            self.skipTest("langchain-core is not installed. Skipping LangChain tests.")

    def test_workflow_has_seven_named_stages(self):
        """Workflow contains all 7 named, composable Runnable stages in sequence."""
        workflow = create_investigation_workflow()
        self.assertIsNotNone(workflow)
        expected_stages = [
            "validate_record",
            "retrieve_eligible_evidence",
            "branch_on_retrieval_outcome",
            "extract_measurement",
            "validate_and_align_source_quote",
            "perform_decimal_conversion_and_comparison",
            "produce_investigation_response",
        ]
        # Verify stages by running on sample and checking stage_metrics
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"
        res, tel = investigate_record_langchain(rec_path, extracted_dir=ext_dir, return_telemetry=True)
        metrics = tel.get("stage_metrics", {})
        for stage_name in expected_stages:
            self.assertIn(stage_name, metrics, f"Missing stage '{stage_name}' in pipeline execution")
            self.assertEqual(metrics[stage_name]["invocations"], 1)
            self.assertGreaterEqual(metrics[stage_name]["duration_ms"], 0.0)

    def test_document_representation_and_metadata_preservation(self):
        """Retrieved evidence is represented as LangChain Document preserving metadata and offsets."""
        from scripts.investigate_chain import stage_retrieve_eligible_evidence
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"
        with open(rec_path, "r", encoding="utf-8") as f:
            rec = json.load(f)

        state = {
            "raw_record": rec,
            "extracted_dir": ext_dir,
            "retriever": "baseline",
            "base_response": {},
            "current_record": {},
        }
        res_state = stage_retrieve_eligible_evidence(state)
        docs = res_state.get("evidence_documents")
        self.assertIsNotNone(docs)
        self.assertEqual(len(docs), 1)
        doc = docs[0]
        self.assertIsInstance(doc, Document)
        self.assertIn("Component thickness: 0.8 cm.", doc.page_content)
        self.assertEqual(doc.metadata["document_filename"], "supplier-COMP-001.pdf")
        self.assertEqual(doc.metadata["page_number"], 1)
        self.assertEqual(doc.metadata["component_id"], "COMP-001")
        self.assertEqual(doc.metadata["revision"], "A")

    def test_retrieval_status_preserved_separately_not_empty_list(self):
        """Conflicting evidence preserves status='ambiguous_evidence' separately from documents."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "extracted"
        res, tel = investigate_record_langchain(rec_path, extracted_dir=ext_dir, return_telemetry=True)
        self.assertEqual(res["outcome"], "ambiguous_evidence")
        self.assertEqual(res["retrieval_status"], "ambiguous_evidence")
        self.assertIn("0.8 cm", res["explanation"])
        self.assertIn("1.2 cm", res["explanation"])

    def test_early_abstention_skips_extractor(self):
        """Early abstention (e.g. unknown component or conflicting evidence) invokes extractor 0 times."""
        # Case 5: unknown component
        rec5 = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "record.json"
        ext5 = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "extracted"
        res5, tel5 = investigate_record_langchain(rec5, extracted_dir=ext5, return_telemetry=True)
        self.assertEqual(res5["outcome"], "insufficient_evidence")
        self.assertEqual(tel5.get("extractor_invocations", 0), 0)
        self.assertEqual(res5["extractor"]["status"], "not_invoked")

        # Case 8: conflicting evidence
        rec8 = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "record.json"
        ext8 = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "extracted"
        res8, tel8 = investigate_record_langchain(rec8, extracted_dir=ext8, return_telemetry=True)
        self.assertEqual(res8["outcome"], "ambiguous_evidence")
        self.assertEqual(tel8.get("extractor_invocations", 0), 0)
        self.assertEqual(res8["extractor"]["status"], "not_invoked")

    def test_eligible_case_invokes_extractor_exactly_once(self):
        """Eligible evidence case invokes extractor exactly once."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"
        res, tel = investigate_record_langchain(rec_path, extracted_dir=ext_dir, return_telemetry=True)
        self.assertEqual(res["outcome"], "correction_proposed")
        self.assertEqual(tel.get("extractor_invocations"), 1)
        self.assertEqual(res["extractor"]["status"], "found")


class TestLangChainGuardrailsAndErrorBehavior(unittest.TestCase):
    """Unit tests for model grounding, whitespace alignment, and guardrails via LangChain."""

    def setUp(self):
        if not LANGCHAIN_INSTALLED:
            self.skipTest("langchain-core is not installed. Skipping LangChain tests.")
        self.rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        self.ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

    def test_whitespace_aware_quote_alignment_through_chain(self):
        """Whitespace variations in model quote align successfully to verbatim passage span."""
        mock = FakeGeminiMockExtractor(quote="Component   thickness:   0.8   cm.")
        res = investigate_record(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            orchestration="langchain",
        )
        self.assertEqual(res["outcome"], "correction_proposed")
        self.assertEqual(res["proposed_correction"]["value"], 8.0)
        self.assertEqual(res["evidence"]["quote_alignment"], "whitespace_aligned")
        self.assertEqual(res["evidence"]["supporting_passage"], "Component thickness: 0.8 cm.")
        self.assertEqual(res["evidence"]["model_quote"], "Component   thickness:   0.8   cm.")

    def test_ungrounded_quote_fails_guardrail_and_yields_needs_review(self):
        """Hallucinated or ungrounded model quote triggers guardrail failure without proposing correction."""
        mock = FakeGeminiMockExtractor(quote="Fabricated ungrounded quote 15.0 mm")
        res = investigate_record(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            orchestration="langchain",
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertIn("Ungrounded extraction", res["explanation"])

    def test_mismatched_attribute_fails_guardrail(self):
        """Extractor returning wrong attribute triggers guardrail failure without proposing correction."""
        mock = FakeGeminiMockExtractor(attr="width")
        res = investigate_record(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            orchestration="langchain",
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertIn("Mismatched measurement", res["explanation"])

    def test_unsupported_unit_fails_guardrail(self):
        """Extractor returning unsupported unit triggers guardrail failure without proposing correction."""
        mock = FakeGeminiMockExtractor(unit="inches", quote="Component thickness: 0.8 cm.")
        res = investigate_record(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            orchestration="langchain",
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertIn("Ungrounded extraction", res["explanation"])

        # Direct Guardrail 5 verification where passage and quote contain unsupported unit
        from scripts.investigate_record import validate_extracted_quote_and_guardrails
        g5_res = ExtractorResult(
            status="found",
            value=Decimal("0.5"),
            unit="in",
            measurement_name="thickness",
            quote="thickness: 0.5 in",
        )
        passed, _, _, _, _, exit_resp = validate_extracted_quote_and_guardrails(
            extractor_res=g5_res,
            passage="Specifications: thickness: 0.5 in",
            attribute_name="thickness",
            evidence_dict={},
            base_response={},
            extractor_meta={},
        )
        self.assertFalse(passed)
        self.assertEqual(exit_resp["outcome"], "needs_review")
        self.assertIn("unsupported", exit_resp["explanation"])

    def test_model_error_yields_needs_review_without_correction(self):
        """Model error (API failure, safety refusal) returns needs_review without proposing correction."""
        mock = FakeGeminiMockExtractor(status="error", err="Safety blocked output", err_type="PROVIDER_ERROR")
        res = investigate_record(
            self.rec_path,
            extracted_dir=self.ext_dir,
            extractor=mock,
            orchestration="langchain",
        )
        self.assertEqual(res["outcome"], "needs_review")
        self.assertIsNone(res["proposed_correction"])
        self.assertIn("Extraction error", res["explanation"])


class TestLangChainDependencyIsolation(unittest.TestCase):
    """Verify that direct execution runs with zero dependency on LangChain."""

    def test_direct_execution_independent_of_langchain(self):
        """Direct execution succeeds when langchain_core is not present in sys.modules."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

        # Mock absence of langchain_core
        with patch.dict("sys.modules", {"langchain_core": None, "langchain_core.runnables": None}):
            res = investigate_record(rec_path, extracted_dir=ext_dir, orchestration="direct")
            self.assertEqual(res["outcome"], "correction_proposed")
            self.assertEqual(res["proposed_correction"]["value"], 8.0)

    def test_langchain_opt_in_raises_helpful_error_when_missing(self):
        """Opting into langchain when package is missing raises clear ImportError."""
        rec_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        ext_dir = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"

        with patch.dict("sys.modules", {"langchain_core": None, "scripts.investigate_chain": None}):
            with self.assertRaises((ImportError, ModuleNotFoundError)) as ctx:
                investigate_record(rec_path, extracted_dir=ext_dir, orchestration="langchain")


class TestLangChainLivePgVectorIntegration(unittest.TestCase):
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
        if not LANGCHAIN_INSTALLED:
            self.skipTest("langchain-core is not installed.")
        if not getattr(self, "db_available", False):
            self.skipTest("PostgreSQL/pgvector database is not available on localhost:5432.")

    def test_live_pgvector_retrieval_parity(self):
        """Live pgvector retrieval through LangChain matches direct execution exactly."""
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
        self.assertEqual(res_direct["outcome"], res_chain["outcome"])
        self.assertEqual(res_direct["proposed_correction"], res_chain["proposed_correction"])
        self.assertEqual(res_direct["evidence"]["document_filename"], res_chain["evidence"]["document_filename"])
        self.assertEqual(res_direct["evidence"]["context_type"], res_chain["evidence"]["context_type"])
        self.assertEqual(res_direct["evidence"]["context_type"], "chunk")


if __name__ == "__main__":
    unittest.main()
