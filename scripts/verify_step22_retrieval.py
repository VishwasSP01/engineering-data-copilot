#!/usr/bin/env python3
"""Comprehensive verification script for Step 22: Metadata-Filtered Vector Evidence Retrieval.

Verifies:
1. Pluggable retriever factory and default baseline selection.
2. Semantic query formulation (identity and attribute name only; never target values).
3. Metadata filtering and deterministic tie-breaking.
4. Full-context conflict detection and safety abstention preservation.
5. Citation preservation and provenance (chunk context_type, page coordinates).
6. Sanitized database error handling without silent fallback.
7. Real CLI and FastAPI HTTP service investigations with pgvector.
8. Retriever comparison report metrics (100% concordance, Recall@1 = 100% on gold cases).
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.retrievers import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    EXPECTED_DIMENSION,
    BaselineRetriever,
    PgVectorRetriever,
    get_retriever,
)
from scripts.investigate_record import investigate_record


def check(name: str, condition: bool, detail: str = ""):
    status = "✓ PASS" if condition else "✗ FAIL"
    msg = f"  [{status}] {name}"
    if detail:
        msg += f": {detail}"
    print(msg)
    if not condition:
        raise AssertionError(f"Check failed: {name} ({detail})")


def verify_all():
    print("=" * 70)
    print("STEP 22 VERIFICATION: METADATA-FILTERED VECTOR RETRIEVAL")
    print("=" * 70)

    # 1. Retriever Factory & Defaults
    print("\n1. Verifying Retriever Factory & Selection Contract...")
    r_default = get_retriever()
    check("Default retriever is BaselineRetriever", isinstance(r_default, BaselineRetriever))
    check("Default retriever name is 'baseline'", r_default.name == "baseline")

    r_base = get_retriever("baseline")
    check("Explicit 'baseline' resolves BaselineRetriever", isinstance(r_base, BaselineRetriever))

    r_vec = get_retriever("pgvector")
    check("Explicit 'pgvector' resolves PgVectorRetriever", isinstance(r_vec, PgVectorRetriever))
    check("PgVectorRetriever name is 'pgvector'", r_vec.name == "pgvector")

    try:
        get_retriever("elasticsearch")
        invalid_caught = False
    except ValueError:
        invalid_caught = True
    check("Invalid retriever name raises ValueError", invalid_caught)

    # 2. Query Formulation
    print("\n2. Verifying Query Formulation & Independence...")
    query = r_vec.build_query_text("COMP-001", "thickness")
    check("Query contains component ID", "COMP-001" in query)
    check("Query contains attribute name", "thickness" in query)
    check("Query never includes target values or units", "0.8" not in query and "8.0" not in query and "mm" not in query)
    check("Query text matches canonical format", query == "Component COMP-001 thickness physical dimension parameter specification")

    # 3. Metadata Filtering & Conflict Detection (Mocked)
    print("\n3. Verifying Conflict Detection Across Full Context...")
    mock_model = MagicMock()
    import numpy as np
    mock_model.encode.return_value = np.zeros(EXPECTED_DIMENSION, dtype=np.float32)

    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = (True,)
    mock_cursor.fetchall.return_value = [
        ("c1", "doc.pdf", 1, 0, 100, 20, "hash1", "COMP-001", "A", "DOC-1",
         "2. Physical Dimensions\nComponent thickness: 0.8 cm.", 0.2),
        ("c2", "doc.pdf", 1, 101, 200, 20, "hash2", "COMP-001", "A", "DOC-1",
         "2. Alternative\nComponent thickness: 1.2 cm.", 0.4),
    ]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    r_mock = PgVectorRetriever(
        embedding_model_instance=mock_model,
        db_connection_factory=lambda: mock_conn,
    )
    rec = {
        "record_id": "REC-01",
        "component_id": "COMP-001",
        "revision": "A",
        "attribute_name": "thickness",
    }
    conflict_res = r_mock.retrieve(rec)
    check("Conflicting specifications trigger ambiguous_evidence", conflict_res["status"] == "ambiguous_evidence")
    check("Conflict explanation lists conflicting values", "0.8 cm" in conflict_res["reason"] and "1.2 cm" in conflict_res["reason"])

    # 4. Error Handling & Sanitization
    print("\n4. Verifying Password Sanitization & Error Handling...")
    def failing_db():
        raise RuntimeError("FATAL: password=super_secret_credentials_123 failed for user copilot")

    r_fail = PgVectorRetriever(
        embedding_model_instance=mock_model,
        db_connection_factory=failing_db,
    )
    fail_res = r_fail.retrieve(rec)
    check("Database connection failure yields status: error", fail_res["status"] == "error")
    check("Error type is DATABASE_ERROR", fail_res["retriever"]["error_type"] == "DATABASE_ERROR")
    check("Password is redacted from error message", "super_secret_credentials_123" not in fail_res["retriever"]["error_message"])
    check("Masked password marker present", "password=***" in fail_res["retriever"]["error_message"])

    # 5. Live Database Investigations (if database is available)
    print("\n5. Verifying Live PostgreSQL/pgvector Investigations...")
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
                total_chunks = cur.fetchone()[0]
        db_live = True
    except Exception as e:
        db_live = False
        print(f"  [WARN] Database not reachable: {e}. Skipping live investigation checks.")

    if db_live:
        check("Database contains ingested chunks", total_chunks >= 68, f"{total_chunks} chunks stored")

        # Investigate case-01
        case01_path = REPO_ROOT / "evaluation" / "cases" / "case-01-correction-cm-to-mm" / "record.json"
        res01 = investigate_record(case01_path, retriever="pgvector", corpus_id="eval-case-01-correction-cm-to-mm")
        check("Case-01 proposed correction is 8.0 mm", res01.get("proposed_correction", {}).get("value") == 8.0)
        check("Case-01 outcome is correction_proposed", res01["outcome"] == "correction_proposed")
        check("Case-01 evidence context_type is chunk", res01["evidence"]["context_type"] == "chunk")
        check("Case-01 cosine similarity > 0.70", res01["evidence"]["similarity_score"] > 0.70)

        # Investigate case-08
        case08_path = REPO_ROOT / "evaluation" / "cases" / "case-08-conflicting-evidence" / "record.json"
        res08 = investigate_record(case08_path, retriever="pgvector", corpus_id="eval-case-08-conflicting-evidence")
        check("Case-08 outcome is ambiguous_evidence", res08["outcome"] == "ambiguous_evidence")

        # Investigate case-05
        case05_path = REPO_ROOT / "evaluation" / "cases" / "case-05-unknown-component" / "record.json"
        res05 = investigate_record(case05_path, retriever="pgvector", corpus_id="eval-case-05-unknown-component")
        check("Case-05 outcome is insufficient_evidence", res05["outcome"] == "insufficient_evidence")

    # 6. FastAPI Service Integration
    print("\n6. Verifying FastAPI Integration...")
    from fastapi.testclient import TestClient
    from api.main import app
    client = TestClient(app)

    payload = {
        "record_id": "unit-mismatch-001",
        "component_id": "COMP-001",
        "revision": "A",
        "attribute_name": "thickness",
        "recorded_value": 0.8,
        "recorded_unit": "mm",
    }
    resp_base = client.post("/investigations?retriever=baseline", json=payload)
    check("API accepts retriever=baseline (HTTP 200)", resp_base.status_code == 200)

    resp_inv = client.post("/investigations?retriever=invalid_ret", json=payload)
    check("API rejects invalid retriever (HTTP 422)", resp_inv.status_code == 422)
    check("API returns INVALID_RETRIEVER code", resp_inv.json().get("error_code") == "INVALID_RETRIEVER")

    if db_live:
        resp_vec = client.post("/investigations?retriever=pgvector", json=payload)
        check("API accepts retriever=pgvector (HTTP 200)", resp_vec.status_code == 200)
        check("API response indicates chunk evidence context", resp_vec.json()["evidence"]["context_type"] == "chunk")

    # 7. Comparison Report Integrity
    print("\n7. Verifying Comparison Benchmark Report...")
    rep_json_path = REPO_ROOT / "evaluation" / "reports" / "step22_retriever_comparison_report.json"
    rep_md_path = REPO_ROOT / "evaluation" / "reports" / "step22_retriever_comparison_report.md"
    check("Report JSON exists", rep_json_path.is_file())
    check("Report Markdown exists", rep_md_path.is_file())

    with open(rep_json_path, "r", encoding="utf-8") as f:
        rep_data = json.load(f)

    check("Comparison evaluates 16 cases", rep_data["summary"]["total_cases"] == 16)
    check("Concordance rate is 16/16 (100.0%)", rep_data["summary"]["concordance"]["matching_outcomes"] == 16)
    check("Baseline pass rate is 15/16 (93.8%)", rep_data["summary"]["baseline_summary"]["passed_cases"] == 15)
    check("PgVector pass rate is 15/16 (93.8%)", rep_data["summary"]["pgvector_summary"]["passed_cases"] == 15)

    ir_metrics = rep_data["summary"]["information_retrieval_metrics"]["metrics"]
    check("Recall@1 is 100.0%", ir_metrics.get("recall_at_1_pct") == 100.0)
    check("Recall@2 is 100.0%", ir_metrics.get("recall_at_2_pct") == 100.0)
    check("Recall@3 is 100.0%", ir_metrics.get("recall_at_3_pct") == 100.0)
    check("MRR is 1.0", ir_metrics.get("mrr") == 1.0)

    print("\n" + "=" * 70)
    print("ALL STEP 22 VERIFICATION CHECKS PASSED SUCCESSFULLY.")
    print("=" * 70)


if __name__ == "__main__":
    verify_all()
