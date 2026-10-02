# Engineering Data Copilot

An evidence-backed AI assistant that audits engineering database records against authoritative supplier technical documentation (PDF datasheets) to identify, verify, and propose corrections for data-quality discrepancies—specifically measurement unit mismatches.

---

## 1. Problem & Narrowly Scoped Solution

### The Problem
Engineering and manufacturing organizations rely on databases (PLM/ERP) containing component specifications (dimensions, weights, tolerances). When components are entered manually or imported from multiple vendors, **unit mismatches** frequently occur—for example, recording `0.8 mm` in the database when the supplier's engineering datasheet specifies `0.8 cm`. Unchecked unit discrepancies cause costly manufacturing rework, assembly line shutdowns, and safety risks.

### The Narrowly Scoped Solution
**Engineering Data Copilot** automates the discrepancy investigation process with strict safety guardrails:
1. **Document-Grounding**: Matches the component ID and revision to eligible supplier datasheets.
2. **Measurement Extraction**: Extracts the authoritative physical dimension using either a fast deterministic regex extractor or structured Gemini model extraction.
3. **Citation & Grounding Guardrails**: Strictly validates that the extracted value, unit, and quote exist verbatim in the source document page before any action is taken.
4. **Deterministic Mathematics**: Unit conversions (`cm` ↔ `mm`) are executed exclusively via Python `Decimal` arithmetic—**the model is never trusted to perform mathematical calculations**.
5. **Safe Abstention**: Automatically abstains (`insufficient_evidence` or `ambiguous_evidence`) when documents are missing, revisions mismatch, or measurements conflict.

---

## 2. Architecture & Pipeline

```mermaid
flowchart TD
    subgraph Inputs ["Inputs"]
        REC["Engineering Record Input<br/>(Part ID, Rev, Attribute, Recorded Value & Unit)"]
        CORPUS["Supplier Document Corpus<br/>(PDF Datasheets & Extracted Page Text)"]
    end

    subgraph Pipeline ["Investigation Pipeline"]
        EDR["Eligible Document Retrieval<br/>(Filters by Part ID & Rev; passage/section fallback)"]
        
        ABSTAIN["Early Safety Abstention<br/>(insufficient_evidence / ambiguous_evidence)"]
        
        subgraph Extraction ["Measurement Extraction (Pluggable Alternatives)"]
            DET["Deterministic Regex Extractor<br/>(Pattern matching & labelled tuple parsing)"]
            GEM["Live Gemini Extractor<br/>(gemini-3.5-flash-lite, strict JSON schema)"]
        end
        
        SQV["Source-Quote Validation<br/>(Verbatim substring match & whitespace alignment)"]
        DC["Deterministic Arithmetic<br/>(Python Decimal conversion; no model math)"]
        DEC["Decision Outcome<br/>(correction_proposed or no_change)"]
    end

    subgraph Evaluation ["Offline Evaluation & CI"]
        EA["Expected Answer Fixtures<br/>(evaluation/expected/*.json)"]
        CMP["Benchmark Evaluator & Comparator<br/>(Verifies outcomes, proposals & citations)"]
    end

    REC --> EDR
    CORPUS --> EDR
    
    EDR -->|Missing or Conflicting Evidence| ABSTAIN
    EDR -->|Retrieved Evidence Passage/Section| DET
    EDR -->|Retrieved Evidence Passage/Section| GEM
    
    DET -->|Extracted Measurement & Quote| SQV
    GEM -->|Extracted Measurement & Quote| SQV
    
    SQV -->|Validated Grounded Measurement| DC
    DC --> DEC
    
    DEC --> CMP
    ABSTAIN --> CMP
    EA -.->|Ground Truth (Evaluator Only)| CMP
```

---

## 3. Technology Stack

- **Runtime & Language**: Python (tested environments documented below).
- **PDF Extraction**: [`pypdf>=6.19.0`](https://pypi.org/project/pypdf/) — Page-by-page selectable text extraction preserving source filenames and 1-based page numbers.
- **Document Generation**: [`reportlab>=5.0.1`](https://pypi.org/project/reportlab/) — Programmatic generation of reproducible synthetic PDF datasheets with vector typography.
- **Data Validation & Schemas**: [`pydantic>=2.13.5`](https://pypi.org/project/pydantic/) — Strict type validation and JSON schema enforcement for model extraction contracts.
- **Investigation Service API**: [`fastapi>=0.115.0`](https://pypi.org/project/fastapi/) & [`uvicorn>=0.30.0`](https://pypi.org/project/uvicorn/) — Minimal asynchronous HTTP service exposing health and investigation endpoints.
- **Deterministic Arithmetic**: Python standard library `decimal.Decimal` — Precise floating-point-free unit conversions (`cm` ↔ `mm`).
- **Foundation Model SDK**: [`google-genai>=1.47.0`](https://pypi.org/project/google-genai/) — Official Google GenAI SDK using structured JSON schema extraction (`gemini-3.5-flash-lite`).
- **Reproducible Dependencies**: Fully pinned dependency lock via [`requirements-lock.txt`](requirements-lock.txt).
- **Continuous Integration**: GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) running automated offline verification on Python 3.13.

---

## 4. Tested Environments

- **macOS (Darwin arm64)**: Verified locally with **Python 3.9.6**.
- **Linux (`ubuntu-latest` / Ubuntu 24.04 x86_64)**: Verified via automated GitHub Actions CI with **Python 3.13**.

> *Note: Windows and untested Python versions are not claimed without direct empirical verification.*

---

## 5. Fresh-Checkout Quickstart

Follow these steps to set up and verify the project in a clean environment:

```bash
# 1. Clone the repository
git clone https://github.com/VishwasSP01/engineering-data-copilot.git
cd engineering-data-copilot

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install locked dependencies (reproducible build)
pip install -r requirements-lock.txt

# 4. Generate synthetic investigation records and PDFs
python3 scripts/generate_sample.py

# 5. Extract document text into data/extracted/ (gitignored)
python3 scripts/extract_documents.py

# 6. Run the offline verification test suite
python3 scripts/verify_sample.py
```

---

## 6. CLI Investigation: Deterministic Baseline

To investigate an engineering record using the fast, deterministic baseline extractor (zero network calls, sub-millisecond execution):

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

---

## 7. Optional Live Gemini Configuration

To run investigations with live Gemini model extraction:

1. Configure your API key in `.env` (kept strictly gitignored) or in your shell environment:
   ```bash
   GEMINI_API_KEY="your-api-key"
   GEMINI_MODEL="gemini-3.5-flash-lite"
   ```

2. Run the investigation with `--extractor gemini`:
   ```bash
   python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor gemini
   ```

3. **Guardrails Active**: When Gemini is selected, the model is strictly limited to extracting the measurement number, unit, and verbatim supporting quote. The quote is verified against the source PDF, and conversion arithmetic is computed entirely in Python `Decimal`.

---

## 8. FastAPI Investigation Service

The investigation workflow can also be run as an asynchronous HTTP service powered by FastAPI and Uvicorn.

### Start the Service
```bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```

### Interactive API Documentation
- **Swagger UI**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **OpenAPI Schema**: [http://localhost:8000/openapi.json](http://localhost:8000/openapi.json)

### Service Endpoints

#### 1. `GET /health`
A lightweight health check requiring no credentials or external calls:
```bash
curl -s http://localhost:8000/health
```
```json
{
  "status": "healthy",
  "service": "engineering-data-copilot",
  "version": "1.0.0"
}
```

#### 2. `POST /investigations`
Investigate an engineering record against the server-configured supplier document corpus.
- Accepts an engineering record object using the standard record schema.
- Extractor selection: `?extractor=deterministic` (default) or `?extractor=gemini`.
- Example request:
```bash
curl -s -X POST "http://localhost:8000/investigations?extractor=deterministic" \
  -H "Content-Type: application/json" \
  -d '{
    "component_id": "COMP-001",
    "revision": "A",
    "attribute_name": "thickness",
    "recorded_value": 0.8,
    "recorded_unit": "mm"
  }'
```
- Example response:
```json
{
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
    "supporting_passage": "Component thickness: 0.8 cm."
  },
  "extractor": {
    "provider": "deterministic",
    "mode": "deterministic",
    "is_fallback": false,
    "call_duration_ms": 0.2
  },
  "explanation": "Supplier document specifies 0.8 cm, which converts via deterministic arithmetic to 8.0 mm (0.8 cm * 10 mm/cm = 8.0 mm). Recorded value is 0.8 mm. Proposing correction to 8.0 mm."
}
```

### HTTP Status Code Mapping
- **HTTP 200**: All business outcomes, including corrections proposed (`correction_proposed`), agreements (`no_change`), and safe data abstentions (`insufficient_evidence`, `ambiguous_evidence`, `needs_review`).
- **HTTP 422**: Malformed request payload (missing required fields, non-numeric values, or unknown extractor).
- **HTTP 503**: Requested provider not configured (`PROVIDER_NOT_CONFIGURED`, e.g. missing API credentials or dependencies).
- **HTTP 502**: Upstream AI provider request failure (`PROVIDER_REQUEST_FAILED`).

---

## 9. Citation-Preserving Document Embeddings

Step 20 introduces pretrained semantic embeddings and citation-preserving chunking for supplier technical datasheets without altering default retrieval or connecting a vector database.

### Core Concepts
- **Embeddings**: Dense 384-dimensional mathematical vector representations capturing semantic meaning of technical text spans.
- **Normalization**: Vectors are projected onto a unit hypersphere ($\|v\|_2 = 1.0 \pm 10^{-5}$) so that vector length differences do not distort semantic similarity calculations.
- **Cosine Similarity**: Computed as the dot product between two unit-normalized vectors ($S_C(u, v) = u \cdot v$), measuring the angular alignment between queries and document chunks from -1.0 to 1.0.

### Model & Settings
- **Pretrained Model**: [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2)
- **Pinned HuggingFace Revision**: `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`
- **Embedding Dimension**: 384 finite float32 values
- **Inference Runtime**: CPU inference exclusively (no GPU required, no fine-tuning)
- **Token Limit**: 250 tokens per chunk (leaves margin for `[CLS]` and `[SEP]` special tokens within the 256-token limit, preventing silent truncation)

### First-Download vs. Cached Execution
- **First Run**: Downloads the model weights (~91 MB) from HuggingFace to the local cache (`~/.cache/huggingface/hub/`).
- **Subsequent Runs**: Loads instantaneously from local cache using `local_files_only=True` with zero network requests.

### Setup & Commands
```bash
# 1. Install optional embedding dependencies (keeps core environment lightweight)
pip install -r requirements-embeddings.txt

# 2. Generate citation-preserving chunks and embeddings for the extracted corpus
python3 scripts/embed_documents.py --extracted-dir data/extracted --output-dir data/embeddings

# 3. Run the Step 20 verification suite
python3 scripts/verify_step20_embeddings.py
```

### Generated Artifacts (Gitignored under `data/embeddings/`)
- `chunks.json`: Structured chunks recording verbatim text, 1-based page number, character offsets (`start_char`, `end_char`), token counts, content SHA-256, and authoritative component/revision IDs.
- `embeddings.npy`: Binary NumPy float32 matrix of shape `(num_chunks, 384)`.
- `manifest.json`: Execution metadata, model name and commit SHA, dimensions, normalization flag, and file hashes.

---

## 10. Offline vs. Live Workflows

The repository strictly separates offline verification from live model evaluations:

- **No Gemini API calls during offline verification**: All offline verification suites, mock extractor checks, deterministic evaluations, FastAPI integration tests, and embedding verification run locally with no Gemini API calls.
- **Network Usage Clarification**: While initial environment setup and optional model downloading require network transit to fetch packages and weights, all verification suites and cached runs operate completely offline.
- **Live Gemini Workflows**: Require `GEMINI_API_KEY` and perform live network generation requests to the Gemini API.

| Workflow | Command | Credentials Required? | External Network Calls? | Local Offline Execution? |
|---|---|:---:|:---:|:---:|
| **Comprehensive Offline Verification** | `python3 scripts/verify_sample.py` | None | None | Yes |
| **Mock Extractor & Guardrail Checks** | `python3 scripts/verify_step8_extractor.py` | None | None | Yes |
| **FastAPI Offline Integration Tests** | `python3 -m unittest discover -s tests -p "test_*.py"` | None | None | Yes |
| **Pretrained Embeddings Verification** | `python3 scripts/verify_step20_embeddings.py` | None | None (after initial cache) | Yes |
| **Deterministic Baseline Evaluation (10 cases)** | `python3 scripts/evaluate.py --extractor deterministic --suite baseline` | None | None | Yes |
| **Deterministic Challenge Evaluation (6 cases)** | `python3 scripts/evaluate.py --extractor deterministic --suite challenge` | None | None | Yes |
| **Deterministic Single Investigation** | `python3 scripts/investigate_record.py <record.json> --extractor deterministic` | None | None | Yes |
| **Live Gemini Investigation** | `python3 scripts/investigate_record.py <record.json> --extractor gemini` | `GEMINI_API_KEY` | Yes (1 API call) | No (API transit) |
| **Live Challenge Comparative Benchmark** | `python3 scripts/evaluate.py --extractor both --suite challenge --step 15` | `GEMINI_API_KEY` | Yes (max 6 calls) | No (API transit) |
| **Live Baseline Comparative Benchmark** | `python3 scripts/evaluate.py --extractor both --suite baseline` | `GEMINI_API_KEY` | Yes (max 10 calls) | No (API transit) |

---

## 11. Evaluation Results & Benchmark Suite

The repository contains two evaluation suites testing length unit mismatches (`cm` ↔ `mm`), agreements, unknown components, incorrect revisions, missing measurements, conflicting evidence, unsupported units, and complex layouts.

### Benchmark Summary

| Evaluation Suite | Suite Size | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Primary Finding |
|---|:---:|:---:|:---:|---|
| **Step 10 Baseline Suite** | 10 cases | **10 / 10 (100.0%)** | **10 / 10 (100.0%)** | Providers showed 100% concordance. In 5 cases, retrieval checks safely abstained prior to model call. |
| **Step 15 Challenge Suite** | 6 cases | 5 / 6 (83.3%) | **6 / 6 (100.0%)** | **Gemini demonstrated value (+16.7 pp)** on unstructured sentence prose (`challenge-01`) where regex rules fail. |

> **Evaluation Scope & Limitations Notice**: These results are derived from controlled synthetic test suites designed to expose parser boundaries and test pipeline integration. **They do not constitute a benchmark of generalized accuracy across unconstrained, real-world supplier engineering drawings, CAD files, or scanned documents.**

### Key Comparison: Step 15 Challenge Suite (6 Cases)

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Comparison |
|---|---|---|---|
| **Overall Pass Rate (End-to-End)** | 5 / 6 (83.3%) | **6 / 6 (100.0%)** | **Gemini Higher (+16.7 percentage points)** |
| **Evidence Retrieval Success Rate** | 4 / 4 (100.0%) | 4 / 4 (100.0%) | Identical |
| **Retrieval Abstention Success Rate** | 2 / 2 (100.0%) | 2 / 2 (100.0%) | Identical (saved 33.3% model calls) |
| **Correction Cases** | 2 / 3 (66.7%) | **3 / 3 (100.0%)** | Gemini resolved sentence prose |
| **Agreement Cases (`no_change`)** | 1 / 1 (100.0%) | 1 / 1 (100.0%) | Identical |
| **Abstention Cases** | 2 / 2 (100.0%) | 2 / 2 (100.0%) | Identical |
| **Citation Validity** | 4 / 4 (100.0%) | 4 / 4 (100.0%) | Identical (4/4 valid citations) |
| **Model Requests** | 0 / 6 | 4 attempted / 4 completed | Zero retries; 2 cases safely skipped |
| **Median Latency (All Cases)** | 0.48 ms | 813.33 ms | Deterministic is faster |
| **Median Latency (Model-Called)** | N/A | 880.62 ms | Network API transit |
| **Median Latency (Non-Model Cases)** | 0.48 ms | 0.23 ms | Local early abstention |
| **Token Usage** | 0 tokens | 1,395 tokens (1,142 prompt, 253 candidate) | Across 4 live calls |

### Evaluation Reports
- [evaluation/reports/step15_challenge_comparison_report.md](evaluation/reports/step15_challenge_comparison_report.md): Step 15 side-by-side comparative report (Deterministic vs. Live Gemini after validation improvements).
- [evaluation/reports/step15_challenge_comparison_report.json](evaluation/reports/step15_challenge_comparison_report.json): Machine-readable Step 15 comparison JSON.
- [evaluation/reports/challenge_comparison_report.md](evaluation/reports/challenge_comparison_report.md): Step 13 side-by-side comparative report (Deterministic vs. Gemini on challenge suite).
- [evaluation/reports/challenge_comparison_report.json](evaluation/reports/challenge_comparison_report.json): Machine-readable Step 13 comparison JSON.
- [evaluation/reports/challenge_report.md](evaluation/reports/challenge_report.md): Detailed Step 12 challenge suite report and limitation analysis.
- [evaluation/reports/challenge_report.json](evaluation/reports/challenge_report.json): Machine-readable challenge evaluation JSON.
- [evaluation/reports/comparison_report.md](evaluation/reports/comparison_report.md): Markdown comparison report with side-by-side per-case results (Step 10 baseline).
- [evaluation/reports/comparison_report.json](evaluation/reports/comparison_report.json): Machine-readable comparative benchmark JSON (Step 10 baseline).
- [evaluation/reports/live_investigation_report.md](evaluation/reports/live_investigation_report.md): Step 9 single live investigation report and attempt history.
- [evaluation/reports/evaluation_report.md](evaluation/reports/evaluation_report.md): Deterministic baseline evaluation report (10 cases).

---

## 12. Continuous Integration (CI)

An automated GitHub Actions workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on all pushes and pull requests targeting the `main` branch.

### CI Guarantees
1. **Environment Setup**: Provisions Python 3.13 on `ubuntu-latest` and installs dependencies from [`requirements-lock.txt`](requirements-lock.txt).
2. **Data & Text Extraction**: Generates synthetic investigation records and extracts document text page-by-page into `data/extracted/`.
3. **Mock & Schema Validation**: Runs [`scripts/verify_step8_extractor.py`](scripts/verify_step8_extractor.py) verifying Pydantic schema validation, prompt boundaries, and 7 mock scenarios.
4. **Comprehensive Regression Suite**: Runs [`scripts/verify_sample.py`](scripts/verify_sample.py) verifying sample validity, text extraction, retrieval, conversion arithmetic, whitespace quote alignment, labelled tuple binding, immutability, and offline replay.
5. **Offline API & Chunking Tests**: Runs `python -m unittest discover -s tests -p "test_*.py"` verifying API endpoints, verbatim citation-preserving chunking boundaries, and document identity safety rejection rules.
6. **Deterministic Benchmark Evaluations**:
   - Baseline Suite: Asserts 10/10 expected pass rate (`scripts/evaluate.py --extractor deterministic --suite baseline`).
   - Challenge Suite: Verifies 5/6 expected pass rate (`scripts/evaluate.py --extractor deterministic --suite challenge`), preserving the known `challenge-01` sentence regex limitation while failing if any unexpected regression occurs.
7. **Artifact Archival**: Uploads all generated reports in `evaluation/reports/` as workflow run artifacts.
8. **Zero Credentials**: Runs strictly offline without requiring or accepting `GEMINI_API_KEY`.

---

## 13. Limitations & Deferred Features

To maintain reliability, security, and auditability, the project's scope is strictly bounded:

### What Is Not Implemented
- **No Vector Database or Vector Retrieval**: Pretrained document embeddings (`sentence-transformers/all-MiniLM-L6-v2`) generate dense vector representations and citation chunks offline, but are not yet connected to a vector database or active retrieval pipeline. Active retrieval currently operates via deterministic metadata filtering (part number, revision) and verbatim text matching.
- **No OCR for Raster Scans**: Documents must contain selectable digital text (`pypdf` extraction); scanned raster PDFs or image-only drawings are not supported.
- **No Multi-Turn Chat or Autonomous Agents**: The investigation workflow is a deterministic, single-turn audit pipeline, not an interactive conversational agent.
- **No Direct Database Mutation**: The tool generates proposed correction payloads; it does not write directly to production ERP or PLM systems.
- **No Web Frontend UI**: The project exposes a CLI and a minimal FastAPI investigation service (`api/main.py`), but does not provide an interactive frontend web UI.

---

## 14. Project Documentation

- [docs/DEMO.md](docs/DEMO.md): Interactive CLI walkthrough and interview demonstration guide.
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): Complete project brief, problem definition, scope, JSON schemas, evaluation criteria, and deferred features.
- [docs/PROGRESS.md](docs/PROGRESS.md): Step-by-step progress tracking, verification logs, and milestone history.
