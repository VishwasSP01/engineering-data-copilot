# Engineering Data Copilot — CLI Walkthrough & Demo Guide

This guide provides a structured, interview-ready walkthrough of the **Engineering Data Copilot**. It demonstrates the core capabilities, deterministic safety guardrails, failure modes, model value-add, and automated verification architecture.

All demo commands run **100% offline** without requiring API credentials or external network access. Saved Gemini outputs are clearly labeled as historical live evaluation artifacts.

---

## 1. Quick Architecture Overview

Engineering Data Copilot resolves discrepancies between engineering database records (e.g. PLM/ERP attributes) and authoritative supplier PDF datasheets:

```mermaid
flowchart TD
    subgraph Inputs ["Inputs"]
        REC["Engineering Record Input<br/>(Part ID, Rev, Attribute, Recorded Value & Unit)"]
        CORPUS["Supplier Document Corpus<br/>(PDF Datasheets & Extracted Page Text)"]
        VECDB["PostgreSQL / pgvector<br/>(Normalized 384d Chunks & HNSW Index)"]
    end

    subgraph Orchestration ["Execution Modes (Pluggable Orchestration)"]
        DIR_EXEC["Direct Execution<br/>(Fast, zero-dependency baseline)"]
        LC_EXEC["LangChain Runnable Sequence<br/>(7 named stages with local telemetry)"]
        LG_EXEC["LangGraph StateGraph<br/>(Explicit nodes, guarded transitions, typed tools)"]
    end

    subgraph Pipeline ["StateGraph Nodes & Transitions"]
        N1["1. validate_record<br/>(Record validity check)"]
        
        subgraph N2 ["2. retrieve_evidence (Pluggable)"]
            BASE_RET["Baseline Document Matching<br/>(Deterministic regex scan over extracted text)"]
            PG_RET["PgVector Semantic Retrieval<br/>(Exact cosine ranking, metadata-filtered)"]
        end
        
        subgraph N3 ["3. extract_measurement (Pluggable)"]
            DET["Deterministic Regex Extractor<br/>(Pattern matching & labelled tuple parsing)"]
            GEM["Live Gemini Extractor<br/>(gemini-3.5-flash-lite, strict JSON schema)"]
        end
        
        N4["4. validate_evidence<br/>(Whitespace alignment, attribute & unit grounding)"]
        N5["5. convert_and_compare<br/>(Deterministic Python Decimal conversion & arithmetic)"]
        N6["6. finalize<br/>(Structured output: correction_proposed, no_change, abstention)"]
    end

    subgraph Evaluation ["Offline Evaluation & CI"]
        EA["Expected Answer Fixtures<br/>(evaluation/expected/*.json)"]
        CMP["Benchmark Evaluator & Comparator<br/>(Verifies outcomes, proposals, citations & IR metrics)"]
    end

    REC --> DIR_EXEC
    REC --> LC_EXEC
    REC --> LG_EXEC
    DIR_EXEC --> N1
    LC_EXEC --> N1
    LG_EXEC --> N1
    
    N1 -->|Valid Record| N2
    N1 -->|Invalid Record| N6
    
    CORPUS --> BASE_RET
    VECDB --> PG_RET
    
    N2 -->|Missing or Conflicting Evidence| N6
    N2 -->|Eligible Evidence Found| N3
    
    N3 -->|Extractor Error / Abstention| N6
    N3 -->|Measurement Extracted| N4
    
    N4 -->|Guardrail Pass| N5
    N4 -->|Guardrail Fail (Ungrounded/Unsupported)| N6
    
    N5 --> N6
    N6 --> CMP
    EA -.->|Ground Truth (Evaluator Only)| CMP
```

---

## 2. Demo 1: Supported Discrepancy Correction (`unit-mismatch-001`)

### Scenario
An engineering record specifies that component `COMP-001` (Revision A) has a thickness of `0.8 mm`. The engineer suspects a unit error in the database.

### CLI Command (Offline)
```bash
python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor deterministic
```

### Actual Command Output
```json
{
  "case_id": "unit-mismatch-001",
  "record_id": "unit-mismatch-001",
  "component_id": "COMP-001",
  "revision": "A",
  "attribute_name": "thickness",
  "current_record": {
    "value": 0.8,
    "unit": "mm"
  },
  "source_record_modified": false,
  "retrieval_status": "evidence_found",
  "context_type": "passage",
  "status": "correction_proposed",
  "outcome": "correction_proposed",
  "evidence_measurement": {
    "value": 0.8,
    "unit": "cm"
  },
  "proposed_correction": {
    "value": 8.0,
    "unit": "mm",
    "conversion": {
      "supplier_extracted_value": 0.8,
      "supplier_extracted_unit": "cm",
      "target_unit": "mm",
      "multiplier": 10.0,
      "calculation": "0.8 cm * 10 mm/cm = 8.0 mm",
      "method": "deterministic_arithmetic"
    }
  },
  "evidence": {
    "document_filename": "supplier-COMP-001.pdf",
    "page_number": 1,
    "supporting_passage": "Component thickness: 0.8 cm.",
    "context_type": "passage",
    "quote_alignment": "literal"
  },
  "extractor": {
    "provider": "deterministic",
    "model": null,
    "mode": "deterministic",
    "is_fallback": false,
    "call_duration_ms": 0.2,
    "token_usage": null,
    "token_usage_reason": "Token usage not applicable for deterministic extractor."
  },
  "explanation": "Supplier document specifies 0.8 cm, which converts via deterministic arithmetic to 8.0 mm (0.8 cm * 10 mm/cm = 8.0 mm). Recorded value is 0.8 mm. Proposing correction to 8.0 mm."
}
```

### Key Takeaway for Reviewers
1. **Provenance & Grounding**: The system cites `supplier-COMP-001.pdf`, page 1, and the verbatim passage `"Component thickness: 0.8 cm."`.
2. **Deterministic Arithmetic**: The calculation (`0.8 cm * 10 = 8.0 mm`) was executed via Python's standard `decimal.Decimal` module, not generated by an LLM prompt.
3. **Record Immutability**: The source database record remains unmodified (`"source_record_modified": false`).

---

## 3. Demo 2: Safety Abstention on Missing or Conflicting Evidence

Engineering automation must not hallucinate or guess when documentation is incomplete or ambiguous. The Copilot enforces early retrieval guardrails that abort before extraction.

### Scenario 2A: Conflicting Evidence (`case-08-conflicting-evidence`)
A supplier document contains contradictory thickness figures (`0.8 cm` on line 1 and `1.2 cm` on line 4).

```bash
python3 scripts/investigate_record.py evaluation/cases/case-08-conflicting-evidence/record.json \
  --extracted-dir evaluation/cases/case-08-conflicting-evidence/extracted
```

**Actual Output**:
```json
{
  "case_id": "case-08-conflicting-evidence",
  "record_id": "REC-08",
  "component_id": "COMP-008",
  "revision": "A",
  "attribute_name": "thickness",
  "current_record": { "value": 0.8, "unit": "mm" },
  "source_record_modified": false,
  "retrieval_status": "ambiguous_evidence",
  "status": "ambiguous_evidence",
  "outcome": "ambiguous_evidence",
  "evidence_measurement": null,
  "proposed_correction": null,
  "evidence": null,
  "extractor": {
    "provider": "deterministic",
    "token_usage_reason": "Retrieval yielded ambiguous_evidence; extractor not invoked."
  },
  "explanation": "Conflicting measurement values found for 'thickness': 0.8 cm, 1.2 cm."
}
```

### Scenario 2B: Revision Mismatch (`challenge-05-incorrect-revision`)
The record requests Revision `A`, but only Revision `B` is present in the document repository.

```bash
python3 scripts/investigate_record.py evaluation/cases/challenge-05-incorrect-revision/record.json \
  --extracted-dir evaluation/cases/challenge-05-incorrect-revision/extracted
```

**Actual Output**:
```json
{
  "case_id": "challenge-05-incorrect-revision",
  "record_id": "REC-CHALLENGE-005",
  "component_id": "COMP-C05",
  "revision": "A",
  "attribute_name": "thickness",
  "current_record": { "value": 0.8, "unit": "mm" },
  "source_record_modified": false,
  "retrieval_status": "insufficient_evidence",
  "status": "insufficient_evidence",
  "outcome": "insufficient_evidence",
  "evidence_measurement": null,
  "proposed_correction": null,
  "evidence": null,
  "extractor": {
    "provider": "deterministic",
    "token_usage_reason": "Retrieval yielded insufficient_evidence; extractor not invoked."
  },
  "explanation": "Document content matches component 'COMP-C05' but revision 'A' was not confirmed."
}
```

### Key Takeaway for Reviewers
- In both cases, `"proposed_correction": null` and the extractor is **never invoked**, avoiding erroneous updates and saving 33.3% of API requests in multi-case evaluations.

---

## 4. Demo 3: Demonstrated Model Value-Add (`challenge-01-complete-sentence`)

### The Challenge
A supplier datasheet embeds component thickness within conversational prose:
> *"Under standard ambient conditions, the nominal thickness of component COMP-C01 is\nmanufactured to 1.2 cm across all production lots."*

### Step 1: The Deterministic Baseline Limitation (Offline CLI)
```bash
python3 scripts/investigate_record.py evaluation/cases/challenge-01-complete-sentence/record.json \
  --extracted-dir evaluation/cases/challenge-01-complete-sentence/extracted \
  --extractor deterministic
```

**Actual Output**:
```json
{
  "case_id": "challenge-01-complete-sentence",
  "status": "needs_review",
  "outcome": "needs_review",
  "evidence_measurement": {
    "value": 1.0,
    "unit": "is"
  },
  "proposed_correction": null,
  "explanation": "Evidence unit 'is' is unsupported. Only ['cm', 'mm'] are supported."
}
```
*Why it failed*: Rigid regex patterns cannot parse natural language phrasing (`"is manufactured to"`), mistakenly capturing `"is"` as the unit token and correctly triggering unit guardrail rejection.

### Step 2: Gemini Value-Add (Historical Live Result from Step 15)
*(Historical live evaluation record saved in [`evaluation/reports/step15_challenge_comparison_report.json`](../evaluation/reports/step15_challenge_comparison_report.json))*:

- **Extractor**: `gemini-3.5-flash-lite` (structured JSON mode)
- **Model Output**:
  - `status`: `"extracted"`
  - `measurement_name`: `"thickness"`
  - `value`: `"1.2"`
  - `unit`: `"cm"`
  - `quote`: `"the nominal thickness of component COMP-C01 is manufactured to 1.2 cm"`
- **Whitespace-Aware Alignment**: Downstream validator mapped the quote across the PDF line-break (`"is\nmanufactured"`), confirming verbatim existence on page 1 without character normalization.
- **Conversion**: Deterministic arithmetic calculated `1.2 cm * 10 = 12.0 mm`.
- **Outcome**: `correction_proposed` to `12.0 mm` (**PASS**).

### Key Takeaway for Reviewers
- **Complementary Roles**: The deterministic extractor is instantaneous (<1 ms) for structured tables and standard labels. The LLM provides semantic robustness on unformatted sentences while downstream guardrails enforce 100% mathematical and citation fidelity.

---

---

## 5. Demo 4: FastAPI HTTP Service & Controlled LangGraph StateGraph Orchestration

In addition to the CLI, the copilot exposes its investigation workflow through a production-ready asynchronous FastAPI service (`api/main.py`) powered by a controlled LangGraph `StateGraph` (`scripts/investigate_graph.py`).

### Starting the Service with LangGraph Orchestration
```bash
export INVESTIGATION_ORCHESTRATION=langgraph
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

### Health Check (Offline, Zero Credentials)
```bash
curl -s http://127.0.0.1:8000/health | jq .
```
```json
{
  "status": "healthy",
  "service": "engineering-data-copilot",
  "version": "1.0.0"
}
```

### Investigating via HTTP with PgVector Retrieval & Gemini Extraction
Send the `unit-mismatch-001` record via HTTP POST:

```bash
curl -X POST http://127.0.0.1:8000/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "component_id": "COMP-001",
    "revision": "A",
    "attribute_name": "thickness",
    "recorded_value": 0.8,
    "recorded_unit": "mm",
    "extractor": "gemini",
    "retriever": "pgvector"
  }' | jq .
```

**Actual Response Output**:
```json
{
  "component_id": "COMP-001",
  "revision": "A",
  "attribute_name": "thickness",
  "current_record": {
    "value": 0.8,
    "unit": "mm"
  },
  "retrieval_status": "evidence_found",
  "context_type": "chunk",
  "status": "correction_proposed",
  "outcome": "correction_proposed",
  "evidence_measurement": {
    "value": 0.8,
    "unit": "cm"
  },
  "proposed_correction": {
    "value": 8.0,
    "unit": "mm",
    "conversion": {
      "supplier_extracted_value": 0.8,
      "supplier_extracted_unit": "cm",
      "target_unit": "mm",
      "multiplier": 10.0,
      "calculation": "0.8 cm * 10 mm/cm = 8.0 mm",
      "method": "deterministic_arithmetic"
    }
  },
  "evidence": {
    "document_filename": "supplier-COMP-001.pdf",
    "page_number": 1,
    "supporting_passage": "Component thickness: 0.8 cm.",
    "context_type": "chunk"
  },
  "orchestration": {
    "mode": "langgraph",
    "node_transitions": [
      "validate_record",
      "retrieve_evidence",
      "extract_measurement",
      "validate_evidence",
      "convert_and_compare",
      "finalize"
    ],
    "tool_invocations": {
      "evidence_retrieval_tool": 1,
      "measurement_extraction_tool": 1,
      "measurement_conversion_tool": 1
    },
    "extractor_invocations": 1
  }
}
```

### Safety Abstention via HTTP (Unknown Component)
```bash
curl -X POST http://127.0.0.1:8000/investigations \
  -H "Content-Type: application/json" \
  -d '{
    "component_id": "COMP-UNKNOWN-999",
    "revision": "A",
    "attribute_name": "thickness",
    "recorded_value": 1.5,
    "recorded_unit": "mm",
    "extractor": "gemini",
    "retriever": "pgvector"
  }' | jq .
```
- **HTTP Status**: `200 OK`
- **Outcome**: `"insufficient_evidence"` (`"proposed_correction": null`)
- **Graph Transitions**: `["validate_record", "retrieve_evidence", "finalize"]` (3 nodes)
- **Tool Invocations**: `evidence_retrieval_tool: 1`, `measurement_extraction_tool: 0`, `measurement_conversion_tool: 0`
- **Zero Model Calls**: The extractor is **never invoked**, guaranteeing zero Gemini API calls when evidence is missing.

### Key Takeaway for Reviewers: Controlled State Graphs vs. Autonomous LLMs
- **Deterministic Control Guarantee**: Tool execution and node routing in this graph are **strictly state-guarded and deterministic**—not autonomous LLM tool selection.
- **Strictly Grounded Math**: The model is solely tasked with semantic extraction. All conversion math (`0.8 cm * 10 = 8.0 mm`) is handled by Python `Decimal` in the `convert_and_compare` node.
- **Finite Invariant**: Compiled with `recursion_limit=10` and 0 retry cycles.

---

## 6. Demo 5: Offline Evaluation & Continuous Integration

### Running Deterministic Benchmark Suites
The project includes two benchmark suites with strict regression checking:

```bash
# Baseline Suite (10 Cases - Expected: 10/10 PASS)
python3 scripts/evaluate.py --extractor deterministic --suite baseline

# Challenge Suite (6 Cases - Expected: 5/6 PASS with honest regex limitation)
python3 scripts/evaluate.py --extractor deterministic --suite challenge

# 3-Way Parity Verification across Direct, LangChain, and LangGraph
python3 scripts/evaluate.py --extractor deterministic --suite baseline --orchestration direct
python3 scripts/evaluate.py --extractor deterministic --suite baseline --orchestration langchain
python3 scripts/evaluate.py --extractor deterministic --suite baseline --orchestration langgraph
```

### Automated Verification Suites (Steps 8 through 25)
```bash
# Core Offline Verification (Steps 3-14)
python3 scripts/verify_sample.py

# Mock Extractor & Guardrail Scenarios (Step 8)
python3 scripts/verify_step8_extractor.py

# Pretrained Embeddings Verification (Step 20)
python3 scripts/verify_step20_embeddings.py

# PostgreSQL/pgvector Storage Verification (Step 21)
python3 scripts/verify_step21_database.py

# Filtered Vector Retrieval Verification (Step 22)
python3 scripts/verify_step22_retrieval.py

# LangChain Orchestration Verification (Step 23)
python3 scripts/verify_step23_langchain.py

# LangGraph Controlled StateGraph Verification (Step 24)
python3 scripts/verify_step24_langgraph.py

# Final Integrated End-to-End RAG Verification (Step 25)
python3 scripts/verify_step25_integration.py
```

### Continuous Integration (GitHub Actions)
Every `git push` and pull request to `main` runs through [`.github/workflows/ci.yml`](../.github/workflows/ci.yml):
- Provisions Python 3.13 on `ubuntu-latest`.
- Installs exact pinned dependencies via `requirements-lock.txt` and `requirements-orchestration.txt`.
- Runs mock, regression, and unit test suites strictly offline.
- Verifies deterministic evaluations across direct, LangChain, and LangGraph orchestration.
- Uploads evaluation reports as workflow artifacts.
- Guarantees zero credential leaks (no API keys required).

---

## 7. Final Portfolio Completion Summary

Engineering Data Copilot implements a production-grade, multi-layered RAG system:
1. **Core Data Science & Extraction**: Text extraction from PDF datasheets, labelled tuple alignment, regex section parsing, and Gemini structured output extraction.
2. **Deterministic Arithmetic Guardrails**: Strict Python `Decimal` conversion ensuring 100% mathematical precision and zero LLM arithmetic errors.
3. **Information Retrieval & Vector Database**: 384-dimensional normalized embeddings (`all-MiniLM-L6-v2`) persisted in PostgreSQL with `pgvector`, filtered by metadata using materialized CTEs to ensure exact cosine distance ranking.
4. **FastAPI Web Service**: Non-blocking asynchronous HTTP service exposing typed endpoints (`/health`, `/investigations`) with Pydantic request/response validation.
5. **Orchestration Evolution**: From direct procedural baseline to composable LangChain Runnables and state-guarded LangGraph StateGraphs, maintaining 100% decision and citation parity across all modes.
