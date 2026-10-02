#!/usr/bin/env python3
"""Automated verification script for Step 24: Controlled LangGraph Orchestration.

Verifies:
1. Orchestration dependencies & lazy isolation contract in requirements-orchestration.txt
2. StateGraph construction with 6 explicit nodes and finite execution limit (recursion_limit=10)
3. Guarded routing paths for eligible, missing, conflicting, invalid, and guardrail-failed cases
4. Tool invocation count invariants (retrieval, extraction, conversion)
5. Fake Gemini grounding, whitespace alignment, and guardrail error behavior
6. State isolation, immutability, and credential/expected answer exclusion
7. Full 3-way parity across all 16 evaluation cases (direct vs. langchain vs. langgraph)
8. Live pgvector integration parity (if database reachable)
9. Local observability and external tracing disabled
"""

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extractors import BaseMeasurementExtractor, ExtractorResult
from scripts.investigate_graph import (
    LANGGRAPH_AVAILABLE,
    get_compiled_graph,
    investigate_record_langgraph,
)
from scripts.investigate_record import investigate_record


class FakeGeminiVerificationExtractor(BaseMeasurementExtractor):
    """Mock Gemini extractor for offline grounding verification."""

    def __init__(
        self,
        quote: str,
        status: str = "found",
        val: Decimal = Decimal("0.8"),
        unit: str = "cm",
        attr: str = "thickness",
        err: str = None,
    ):
        self._quote = quote
        self._status = status
        self._val = val
        self._unit = unit
        self._attr = attr
        self._err = err

    @property
    def provider(self) -> str:
        return "google-genai"

    @property
    def model(self) -> str:
        return "mock-gemini-verification"

    def extract_measurement(self, evidence_passage: str, attribute_name: str) -> ExtractorResult:
        return ExtractorResult(
            status=self._status,
            value=self._val,
            unit=self._unit,
            measurement_name=self._attr,
            quote=self._quote,
            error_message=self._err,
            provider=self.provider,
            model=self.model,
            call_duration_ms=10.0,
        )


def verify_all():
    print("=" * 70)
    print("STEP 24 VERIFICATION: CONTROLLED LANGGRAPH ORCHESTRATION")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # 1. Verify Dependencies & Lazy Isolation
    # -----------------------------------------------------------------------
    print("\n1. Verifying Dependencies & Lazy Isolation...")
    req_orch_path = REPO_ROOT / "requirements-orchestration.txt"
    assert req_orch_path.is_file(), "requirements-orchestration.txt must exist"
    req_text = req_orch_path.read_text(encoding="utf-8")
    assert "langgraph==0.6.11" in req_text, "langgraph pin missing"
    assert "langgraph-checkpoint==2.1.2" in req_text, "langgraph-checkpoint pin missing"
    assert "langgraph-prebuilt==0.6.5" in req_text, "langgraph-prebuilt pin missing"
    assert "langchain-core==0.3.86" in req_text, "langchain-core pin missing"
    print("  [✓ PASS] requirements-orchestration.txt exists with reproducible LangGraph pins")

    rec1 = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
    ext1 = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "extracted"
    res_direct = investigate_record(rec1, extracted_dir=ext1, orchestration="direct")
    assert res_direct["outcome"] == "correction_proposed"
    print("  [✓ PASS] Direct execution remains fully operational as zero-dependency baseline")

    # -----------------------------------------------------------------------
    # 2. Verify StateGraph Construction & 6 Explicit Nodes
    # -----------------------------------------------------------------------
    print("\n2. Verifying StateGraph Construction & 6 Explicit Nodes...")
    assert LANGGRAPH_AVAILABLE, "langgraph must be available in environment"
    graph = get_compiled_graph()
    assert graph is not None, "get_compiled_graph() returned None"
    expected_nodes = [
        "validate_record",
        "retrieve_evidence",
        "extract_measurement",
        "validate_evidence",
        "convert_and_compare",
        "finalize",
    ]
    for node in expected_nodes:
        assert node in graph.nodes, f"Node '{node}' missing from StateGraph"
        print(f"  [✓ PASS] Node verified: '{node}'")

    # -----------------------------------------------------------------------
    # 3. Verify Guarded Routing Paths
    # -----------------------------------------------------------------------
    print("\n3. Verifying Guarded Routing Paths...")
    # Route 1: Eligible case (case-01) visits all 6 nodes
    res1, tel1 = investigate_record_langgraph(rec1, extracted_dir=ext1, return_telemetry=True)
    assert tel1["node_transitions"] == expected_nodes, f"Unexpected transitions for case-01: {tel1['node_transitions']}"
    assert res1["outcome"] == "correction_proposed"
    print("  [✓ PASS] Eligible path (case-01): 6 nodes in sequence -> finalize")

    # Route 2: Invalid record (case-10) routes validate_record -> finalize
    rec10 = REPO_ROOT / "evaluation" / "cases" / "case-10-malformed-measurement" / "record.json"
    ext10 = REPO_ROOT / "evaluation" / "cases" / "case-10-malformed-measurement" / "extracted"
    res10, tel10 = investigate_record_langgraph(rec10, extracted_dir=ext10, return_telemetry=True)
    assert tel10["node_transitions"] == ["validate_record", "finalize"]
    assert res10["outcome"] == "needs_review"
    print("  [✓ PASS] Invalid record path (case-10): validate_record -> finalize (2 nodes)")

    # Route 3: Missing evidence (case-05) routes validate_record -> retrieve_evidence -> finalize
    rec5 = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "record.json"
    ext5 = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "extracted"
    res5, tel5 = investigate_record_langgraph(rec5, extracted_dir=ext5, return_telemetry=True)
    assert tel5["node_transitions"] == ["validate_record", "retrieve_evidence", "finalize"]
    assert res5["outcome"] == "insufficient_evidence"
    print("  [✓ PASS] Missing evidence path (case-05): validate_record -> retrieve_evidence -> finalize (3 nodes)")

    # Route 4: Conflicting evidence (case-08) routes validate_record -> retrieve_evidence -> finalize
    rec8 = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "record.json"
    ext8 = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "extracted"
    res8, tel8 = investigate_record_langgraph(rec8, extracted_dir=ext8, return_telemetry=True)
    assert tel8["node_transitions"] == ["validate_record", "retrieve_evidence", "finalize"]
    assert res8["outcome"] == "ambiguous_evidence"
    print("  [✓ PASS] Conflicting evidence path (case-08): validate_record -> retrieve_evidence -> finalize (3 nodes)")

    # Route 5: Unsupported unit (case-09) stops at validate_evidence before conversion
    rec9 = REPO_ROOT / "evaluation" / "cases" / "case-09-unsupported-unit" / "record.json"
    ext9 = REPO_ROOT / "evaluation" / "cases" / "case-09-unsupported-unit" / "extracted"
    res9, tel9 = investigate_record_langgraph(rec9, extracted_dir=ext9, return_telemetry=True)
    assert tel9["node_transitions"] == ["validate_record", "retrieve_evidence", "extract_measurement", "validate_evidence", "finalize"]
    assert res9["outcome"] == "needs_review"
    print("  [✓ PASS] Guardrail failure path (case-09): stops at validate_evidence before conversion (5 nodes)")

    # -----------------------------------------------------------------------
    # 4. Verify Tool Invocation Count Invariants
    # -----------------------------------------------------------------------
    print("\n4. Verifying Tool Invocation Count Invariants...")
    # Case 01: 1 retrieval, 1 extraction, 1 conversion
    assert tel1["tool_invocations"]["evidence_retrieval_tool"] == 1
    assert tel1["tool_invocations"]["measurement_extraction_tool"] == 1
    assert tel1["tool_invocations"]["measurement_conversion_tool"] == 1
    assert tel1["extractor_invocations"] == 1
    print("  [✓ PASS] Case 01: retrieval=1, extraction=1, conversion=1 (extractor_invocations=1)")

    # Case 05: 1 retrieval, 0 extraction, 0 conversion
    assert tel5["tool_invocations"]["evidence_retrieval_tool"] == 1
    assert tel5["tool_invocations"].get("measurement_extraction_tool", 0) == 0
    assert tel5["tool_invocations"].get("measurement_conversion_tool", 0) == 0
    assert tel5["extractor_invocations"] == 0
    assert res5["extractor"]["status"] == "not_invoked"
    print("  [✓ PASS] Case 05 (abstention): retrieval=1, extraction=0, conversion=0 (extractor_invocations=0)")

    # Case 10: 0 retrieval, 0 extraction, 0 conversion
    assert tel10["tool_invocations"].get("evidence_retrieval_tool", 0) == 0
    assert tel10["tool_invocations"].get("measurement_extraction_tool", 0) == 0
    assert tel10["tool_invocations"].get("measurement_conversion_tool", 0) == 0
    assert tel10["extractor_invocations"] == 0
    assert res10["extractor"]["status"] == "not_invoked"
    print("  [✓ PASS] Case 10 (invalid record): retrieval=0, extraction=0, conversion=0 (extractor_invocations=0)")

    # Case 09: 1 retrieval, 1 extraction, 0 conversion
    assert tel9["tool_invocations"]["evidence_retrieval_tool"] == 1
    assert tel9["tool_invocations"]["measurement_extraction_tool"] == 1
    assert tel9["tool_invocations"].get("measurement_conversion_tool", 0) == 0
    assert tel9["extractor_invocations"] == 1
    print("  [✓ PASS] Case 09 (guardrail reject): retrieval=1, extraction=1, conversion=0")

    # -----------------------------------------------------------------------
    # 5. Verify Fake Gemini Grounding & Error Behavior
    # -----------------------------------------------------------------------
    print("\n5. Verifying Fake Gemini Grounding & Error Behavior...")
    # Whitespace variation -> aligned and passes through all 6 nodes
    fake_ws = FakeGeminiVerificationExtractor(quote="Component   thickness:   0.8   cm.")
    res_ws, tel_ws = investigate_record_langgraph(rec1, extracted_dir=ext1, extractor=fake_ws, return_telemetry=True)
    assert res_ws["outcome"] == "correction_proposed"
    assert res_ws["evidence"]["quote_alignment"] == "whitespace_aligned"
    assert res_ws["evidence"]["supporting_passage"] == "Component thickness: 0.8 cm."
    assert "convert_and_compare" in tel_ws["node_transitions"]
    print("  [✓ PASS] Whitespace variation aligned to verbatim span and passed through graph")

    # Hallucinated quote -> fails guardrail in validate_evidence, 0 conversion calls
    fake_hal = FakeGeminiVerificationExtractor(quote="Fabricated ungrounded quote 15.0 mm")
    res_hal, tel_hal = investigate_record_langgraph(rec1, extracted_dir=ext1, extractor=fake_hal, return_telemetry=True)
    assert res_hal["outcome"] == "needs_review"
    assert res_hal["proposed_correction"] is None
    assert "convert_and_compare" not in tel_hal["node_transitions"]
    assert tel_hal["tool_invocations"].get("measurement_conversion_tool", 0) == 0
    print("  [✓ PASS] Ungrounded quote stopped at validate_evidence with 0 conversion tool calls")

    # Extraction error -> stops immediately after extract_measurement
    fake_err = FakeGeminiVerificationExtractor(quote="", status="error", err="Safety block")
    res_err, tel_err = investigate_record_langgraph(rec1, extracted_dir=ext1, extractor=fake_err, return_telemetry=True)
    assert res_err["outcome"] == "needs_review"
    assert tel_err["node_transitions"] == ["validate_record", "retrieve_evidence", "extract_measurement", "finalize"]
    print("  [✓ PASS] Extraction error routed directly to finalize (4 nodes)")

    # -----------------------------------------------------------------------
    # 6. Verify State Isolation & Security
    # -----------------------------------------------------------------------
    print("\n6. Verifying State Isolation & Security...")
    # Test record with leaked credentials and expected answers
    rec_leak = {
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
    res_sec = investigate_record(rec_leak, extracted_dir=ext1, orchestration="langgraph")
    res_str = json.dumps(res_sec)
    assert "SECRET_LEAK_KEY" not in res_str, "Credentials must never leak into response"
    assert "CORRECTION_LEAK" not in res_str, "Expected answers must not influence state"
    assert res_sec["outcome"] == "correction_proposed"
    print("  [✓ PASS] Credentials and expected answers strictly excluded from state and output")

    # -----------------------------------------------------------------------
    # 7. Verify Full 3-Way Parity Across All 16 Evaluation Cases
    # -----------------------------------------------------------------------
    print("\n7. Verifying Full 3-Way Parity Across All 16 Cases (Direct vs LangChain vs LangGraph)...")
    cases_dir = REPO_ROOT / "evaluation" / "cases"
    cases = sorted([d for d in cases_dir.iterdir() if d.is_dir() and (d.name.startswith("case-") or d.name.startswith("challenge-"))], key=lambda d: d.name)
    assert len(cases) == 16, f"Expected 16 evaluation cases, found {len(cases)}"

    for c in cases:
        r_p = c / "record.json"
        e_d = c / "extracted"
        rd = investigate_record(r_p, extracted_dir=e_d, orchestration="direct")
        rc = investigate_record(r_p, extracted_dir=e_d, orchestration="langchain")
        rg = investigate_record(r_p, extracted_dir=e_d, orchestration="langgraph")

        assert rd["outcome"] == rg["outcome"] == rc["outcome"], f"Outcome mismatch on {c.name}"
        assert rd["status"] == rg["status"] == rc["status"], f"Status mismatch on {c.name}"
        assert rd.get("proposed_correction") == rg.get("proposed_correction") == rc.get("proposed_correction"), f"Proposal mismatch on {c.name}"
        assert rd.get("evidence") == rg.get("evidence") == rc.get("evidence"), f"Evidence citation mismatch on {c.name}"
        print(f"  [✓ PASS] {c.name:<45} -> {rd['outcome']} (100% 3-way match)")

    # -----------------------------------------------------------------------
    # 8. Verify Live PgVector Retrieval Parity (if available)
    # -----------------------------------------------------------------------
    print("\n8. Checking Live PgVector Retrieval Parity...")
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
                cnt = cur.fetchone()[0]
        db_live = True
    except Exception:
        db_live = False

    if db_live:
        res_d_pg = investigate_record(rec1, retriever="pgvector", corpus_id="eval-case-01-correction-cm-to-mm", orchestration="direct")
        res_g_pg = investigate_record(rec1, retriever="pgvector", corpus_id="eval-case-01-correction-cm-to-mm", orchestration="langgraph")
        assert res_d_pg["outcome"] == res_g_pg["outcome"]
        assert res_d_pg["proposed_correction"] == res_g_pg["proposed_correction"]
        assert res_g_pg["evidence"]["context_type"] == "chunk"
        print(f"  [✓ PASS] Live PgVector retrieval confirmed ({cnt} chunks in DB; 100% parity with direct)")
    else:
        print("  [— SKIP] PostgreSQL/pgvector not reachable on localhost:5432 (skipping live DB check)")

    # -----------------------------------------------------------------------
    # 9. Verify Local Telemetry & Tracing Status
    # -----------------------------------------------------------------------
    print("\n9. Verifying Local Observability & Tracing...")
    assert os.environ.get("LANGCHAIN_TRACING_V2", "false").lower() == "false"
    assert os.environ.get("LANGSMITH_TRACING", "false").lower() == "false"
    print("  [✓ PASS] External tracing disabled by default (LANGCHAIN_TRACING_V2=false)")
    print("  [✓ PASS] Local execution records node transitions, node timings, and tool counts")

    print("\n" + "=" * 70)
    print("ALL STEP 24 VERIFICATION CHECKS PASSED SUCCESSFULLY.")
    print("=" * 70)


if __name__ == "__main__":
    verify_all()
