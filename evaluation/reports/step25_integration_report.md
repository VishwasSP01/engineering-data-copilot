# Step 25: Final Integrated Verification & Portfolio Completion

**Evaluation Type**: Full-Stack End-to-End HTTP Integration Test  
**Timestamp**: `2026-10-02T14:29:48Z`  
**Commit**: `350c28050aeb17b721a6bca5d6c3f5982c4e4fc6`  
**Python**: `3.9.6` (`darwin`)  
**Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (SHA: `1110a243fd`)  
**Vector Database**: `PostgreSQL 16.10 / pgvector 0.8.0`  
**Foundation Model**: `gemini-3.5-flash-lite` (via official `google-genai` SDK)  
**Orchestration Engine**: `LangGraph StateGraph` (`INVESTIGATION_ORCHESTRATION=langgraph`)  

> **Evaluation Scope & Limitations Notice**:  
> This integration run validates end-to-end functionality across all components (HTTP API $\rightarrow$ LangGraph $\rightarrow$ PgVector $\rightarrow$ Gemini $\rightarrow$ Decimal) on **one live positive discrepancy case** and **one safe abstention case**. It verifies pipeline correctness, citation resolution, and safety invariants. **It does not constitute a broad statistical accuracy benchmark across unconstrained engineering drawings.**

---

## 1. System Inventory & Component Stack

| Layer | Implementation Component | Version / Specification |
|---|---|---|
| **HTTP API Service** | FastAPI / Uvicorn | `fastapi>=0.115.0`, `uvicorn>=0.30.0` (port 8008) |
| **Workflow Orchestration** | LangGraph `StateGraph` | `langgraph==0.6.11`, 6 explicit guarded nodes, `recursion_limit=10` |
| **Vector Database** | PostgreSQL + pgvector | `pgvector/pgvector:0.8.0-pg16`, HNSW index + B-Tree composite index |
| **Filtered Search Strategy** | Exact Cosine Ranking | Parameterized `WITH filtered_chunks AS MATERIALIZED` CTE |
| **Embedding Model** | Sentence Transformers | `all-MiniLM-L6-v2` (`1110a243...`), 384d, normalized, CPU inference |
| **Foundation Model** | Google GenAI SDK | `gemini-3.5-flash-lite`, structured JSON schema, 0 retries (`attempts=1`) |
| **Arithmetic Engine** | Python Standard Library | `decimal.Decimal` (deterministic arithmetic, zero LLM math) |

---

## 2. End-to-End Integration Requests Summary

| Case ID | Input Record | Target Attribute | Retriever | Extractor | HTTP Status | Business Outcome | Latency (ms) | Live Model Calls | Tokens Used |
|---|---|---|---|---|:---:|---|:---:|:---:|:---:|
| **`unit-mismatch-001`** | `COMP-001` (rev A, 0.8 mm) | `thickness` | `pgvector` | `gemini` | **200 OK** | `correction_proposed` (8.0 mm) | 4008.65 | 1 | 377 |
| **`test-unknown-component-001`** | `COMP-NONEXISTENT-999` (rev A) | `thickness` | `pgvector` | `gemini` | **200 OK** | `insufficient_evidence` | 71.03 | 0 | 0 (skipped) |

**Cost Summary**: Unknown (`null`). Exact per-token pricing varies by Google Cloud billing tier; estimated API cost is $<\$0.0001$.

---

## 3. Case 1 Trace: Live Discrepancy Investigation (`unit-mismatch-001`)

### Input Payload
```json
{
  "case_id": "unit-mismatch-001",
  "record_id": "unit-mismatch-001",
  "component_id": "COMP-001",
  "part_number": "COMP-001",
  "revision": "A",
  "attribute_name": "thickness",
  "recorded_value": 0.8,
  "recorded_unit": "mm",
  "document_reference": {
    "document_id": "DOC-SUP-COMP-001",
    "filename": "supplier-COMP-001.pdf",
    "filepath": "data/documents/supplier-COMP-001.pdf"
  },
  "extractor": "gemini",
  "retriever": "pgvector"
}
```

### Graph Execution & Tool Invocations
- **Node Transitions (6 nodes in sequence)**:
  `validate_record -> retrieve_evidence -> extract_measurement -> validate_evidence -> convert_and_compare -> finalize`
- **Tool Invocations**:
  - `evidence_retrieval_tool`: 1 invocation
  - `measurement_extraction_tool`: 1 invocation
  - `measurement_conversion_tool`: 1 invocation
- **Extracted Measurement**: `0.8 cm`
- **Proposed Correction**: `8.0 mm` via `0.8 cm * 10 mm/cm = 8.0 mm`
- **Source Citation**: Document `supplier-COMP-001.pdf`, Page 1, Context: `chunk`
- **Supporting Passage**:
  > *"2. Physical Dimensions & Mechanical Parameters
Mechanical measurements for component ID COMP-001 under standard test conditions (25°C, 50% RH). Note
the primary dimensional measurements recorded below:
Component thickness: 0.8 cm.
Parameter
Nominal Value
Tolerance
Notes
Length
25.0 mm
±0.1 mm
Longitudinal body axis
Width
15.0 mm
±0.1 mm
Transverse body axis
Thickness
0.8 cm
±0.02 cm
Overall substrate height
Substrate Material
96% Al2O3
—
High-purity alumina"*

---

## 4. Case 2 Trace: Unknown Component Abstention (`test-unknown-component-001`)

### Input Payload
```json
{
  "case_id": "test-unknown-component-001",
  "record_id": "test-unknown-001",
  "component_id": "COMP-NONEXISTENT-999",
  "part_number": "COMP-NONEXISTENT-999",
  "revision": "A",
  "attribute_name": "thickness",
  "recorded_value": 1.5,
  "recorded_unit": "mm",
  "extractor": "gemini",
  "retriever": "pgvector"
}
```

### Graph Execution & Safety Short-Circuit
- **Node Transitions (3 nodes)**:
  `validate_record -> retrieve_evidence -> finalize`
- **Tool Invocations**:
  - `evidence_retrieval_tool`: 1 invocation
  - `measurement_extraction_tool`: 0 invocations (**skipped**)
  - `measurement_conversion_tool`: 0 invocations (**skipped**)
- **Outcome**: `insufficient_evidence` (no correction proposed)
- **Explanation**: Component ID 'COMP-NONEXISTENT-999' not found in extracted document content.
- **Safety Invariant Verified**: Extractor was **never invoked**; 0 additional Gemini generation calls made.

---

## 5. File Immutability Verification

| File | SHA-256 Digest | Status |
|---|---|:---:|
| `data/records/unit-mismatch-001.json` | `d8c5492ca8065a66b7642a7f19371ae2c53d8d267a338d3f41adad05bac64fb7` | **UNCHANGED** |
| `data/documents/supplier-COMP-001.pdf` | `5ad384568c1c5966bd157e3d609044efc54ee7544efa184c775ecbdb664ce00e` | **UNCHANGED** |
| `data/extracted/supplier-COMP-001.json` | `20892018dea04b411d2847b2185d23ffdf9f1f36be780cbb4303b8efd1a60029` | **UNCHANGED** |

---

## 6. Portfolio MVP Completion Status

With Step 25 verified:
- [x] **Core Investigation Logic**: Verified across 10 baseline cases (10/10) and 6 challenge cases (6/6 live Gemini).
- [x] **FastAPI Service**: Verified via HTTP with Pydantic validation, error mapping, and async dispatch.
- [x] **Embeddings & Vector Database**: Verified 384d normalized embeddings in PostgreSQL/pgvector with exact filtered search.
- [x] **LangChain & LangGraph Orchestration**: Verified 7-stage Runnable pipeline and 6-node guarded StateGraph with 100% parity.
- [x] **Strict Safety Guardrails**: Citation grounding, Decimal conversion arithmetic, early abstention on missing/conflicting data.
- [x] **Zero Credential Requirement for Offline Verification**: All offline checks and CI runs execute without network or API keys.

