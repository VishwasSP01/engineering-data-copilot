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
        VECDB["PostgreSQL / pgvector<br/>(Normalized 384d Chunks & HNSW Index)"]
    end

    subgraph Orchestration ["Execution Modes (Pluggable Orchestration)"]
        DIR_EXEC["Direct Execution<br/>(Fast, zero-dependency procedural execution)"]
        LC_EXEC["LangChain Runnable Sequence<br/>(Named composable stages with local telemetry)"]
        LG_EXEC["LangGraph StateGraph<br/>(Explicit nodes, guarded transitions, typed tools)"]
    end

    subgraph Pipeline ["StateGraph Nodes & Transitions"]
        N1["1. validate_record<br/>(Value presence, Decimal parseability, supported units)"]
        
        subgraph N2 ["2. retrieve_evidence (evidence_retrieval_tool)"]
            BASE_RET["Baseline Document Matching<br/>(Deterministic regex scan over extracted text)"]
            PG_RET["PgVector Semantic Retrieval<br/>(Exact cosine ranking, metadata-filtered)"]
        end
        
        subgraph N3 ["3. extract_measurement (measurement_extraction_tool)"]
            DET["Deterministic Regex Extractor<br/>(Pattern matching & labelled tuple parsing)"]
            GEM["Live Gemini Extractor<br/>(gemini-3.5-flash-lite, strict JSON schema)"]
        end
        
        N4["4. validate_evidence<br/>(Whitespace alignment, attribute & unit grounding)"]
        N5["5. convert_and_compare (measurement_conversion_tool)<br/>(Deterministic Python Decimal conversion & arithmetic)"]
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

## 3. Technology Stack

- **Runtime & Language**: Python (tested environments documented below).
- **Workflow Orchestration**: [`langchain-core==0.3.86`](https://pypi.org/project/langchain-core/) & [`langgraph==0.6.11`](https://pypi.org/project/langgraph/) — Optional Runnable and StateGraph orchestration engines with explicit guarded conditional branching, typed tool execution, and local telemetry.
- **PDF Extraction**: [`pypdf>=6.19.0`](https://pypi.org/project/pypdf/) — Page-by-page selectable text extraction preserving source filenames and 1-based page numbers.
- **Document Generation**: [`reportlab>=5.0.1`](https://pypi.org/project/reportlab/) — Programmatic generation of reproducible synthetic PDF datasheets with vector typography.
- **Data Validation & Schemas**: [`pydantic>=2.13.5`](https://pypi.org/project/pydantic/) — Strict type validation and JSON schema enforcement for model extraction contracts.
- **Investigation Service API**: [`fastapi>=0.115.0`](https://pypi.org/project/fastapi/) & [`uvicorn>=0.30.0`](https://pypi.org/project/uvicorn/) — Minimal asynchronous HTTP service exposing health and investigation endpoints.
- **Vector Database & Persistence**: [`pgvector/pgvector:0.8.0-pg16`](https://github.com/pgvector/pgvector) — PostgreSQL 16 container with the `vector` extension, HNSW cosine index, and Python drivers (`psycopg[binary]>=3.2.0`, `pgvector>=0.4.0`).
- **Embedding Model**: [`sentence-transformers/all-MiniLM-L6-v2`](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) — 384-dimensional normalized vector representations for document chunks.
- **Deterministic Arithmetic**: Python standard library `decimal.Decimal` — Precise floating-point-free unit conversions (`cm` ↔ `mm`).
- **Foundation Model SDK**: [`google-genai>=1.47.0`](https://pypi.org/project/google-genai/) — Official Google GenAI SDK using structured JSON schema extraction (`gemini-3.5-flash-lite`).
- **Reproducible Dependencies**: Fully pinned dependency lock via [`requirements-lock.txt`](requirements-lock.txt) with optional modular requirements for database (`requirements-database.txt`), embeddings (`requirements-embeddings.txt`), and orchestration (`requirements-orchestration.txt`).
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
- **HTTP 422**: Malformed request payload, invalid extractor name (`INVALID_EXTRACTOR`), or invalid retriever selection (`INVALID_RETRIEVER`).
- **HTTP 503**: Requested provider not configured (`PROVIDER_NOT_CONFIGURED`, e.g. missing API credentials) or database retriever unconfigured (`RETRIEVER_NOT_CONFIGURED`, e.g. missing driver dependencies).
- **HTTP 502**: Upstream AI provider request failure (`PROVIDER_REQUEST_FAILED`) or database service connection failure (`RETRIEVER_SERVICE_ERROR`).

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

## 10. Document Vector Persistence with PostgreSQL & pgvector

Step 21 introduces containerized vector persistence for document chunks, metadata, and 384-dimensional embeddings using PostgreSQL and the `pgvector` extension.

### Architecture & Service Setup
- **Image**: Pinned to [`pgvector/pgvector:0.8.0-pg16`](https://hub.docker.com/r/pgvector/pgvector) (PostgreSQL 16 with pgvector 0.8.0).
- **Persistent Storage**: Named Docker volume `copilot_pgvector_data` mounted at `/var/lib/postgresql/data`.
- **Port & Host**: Bound to `127.0.0.1:${POSTGRES_PORT:-5432}`.
- **Configuration**: Credentials read from `.env` (defaults in `.env.example`). Credentials and passwords are never logged or committed.
- **Health Check**: Configured via `pg_isready -U ${POSTGRES_USER:-copilot_user} -d ${POSTGRES_DB:-copilot_db}` with 3s intervals and 5 retries.

### Schema & Indexing (`scripts/init_db.sql`)
- **Table**: `document_chunks` preserving 17 fields:
  - **Provenance**: `corpus_id`, `chunk_id`, `document_filename`, `page_number`, `start_char`, `end_char`, `token_count`, `content_sha256`.
  - **Authoritative Identifiers**: `component_id`, `revision`, `document_id`.
  - **Content & Configuration**: `text` (verbatim source span), `model_name`, `model_revision`.
  - **Vector**: `embedding vector(384)` storing normalized float32 vectors.
- **Constraints & Indexes**:
  - Unique constraint on `(corpus_id, chunk_id)` guaranteeing idempotent upserts.
  - Composite B-tree index on `(corpus_id, component_id, revision)` for strict metadata filtering.
  - HNSW index on `embedding` using `vector_cosine_ops` for efficient nearest-neighbor searches.

### Database Setup & Ingestion Commands
```bash
# 1. Start the PostgreSQL/pgvector service via Docker Compose
docker compose up -d

# 2. Confirm service health
docker compose ps

# 3. Install optional database driver dependencies
pip install -r requirements-database.txt

# 4. Ingest document chunks and pretrained embeddings
python3 scripts/ingest_embeddings.py

# 5. Run the comprehensive Step 21 verification suite
# (Verifies schema, counts, verbatim fidelity, idempotency, restart persistence, cosine query, and metadata filtering)
python3 scripts/verify_step21_database.py
```

### Stopping and Tearing Down the Database Service
```bash
# Stop containers without removing persistent data:
docker compose stop

# Stop and remove containers and network (preserves named volume copilot_pgvector_data):
docker compose down

# To completely wipe the volume and reset the database:
docker compose down -v
```

### Step 22: Metadata-Filtered Vector Retrieval Integration

In Step 22, PostgreSQL/pgvector was integrated as an active, pluggable retrieval engine (`--retriever pgvector`) alongside the deterministic baseline (`--retriever baseline`, the default):

1. **Index Evaluation Corpora**:
   ```bash
   python3 scripts/index_evaluation_corpora.py
   ```
2. **Run Single Investigation with Vector Retrieval**:
   ```bash
   python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --retriever pgvector --extractor deterministic
   ```
3. **Verify Retriever Mechanics & Safety**:
   ```bash
   python3 scripts/verify_step22_retrieval.py
   ```
4. **Run Retriever Comparative Benchmark (All 16 Cases)**:
   ```bash
   python3 scripts/evaluate.py --retriever both --suite all
   ```

---

## 11. LangChain Workflow Orchestration (Step 23)

In Step 23, an optional LangChain orchestration execution path was introduced using `langchain-core` Runnables, preserving existing business decisions, citation provenance, and error behavior with 100% parity.

### Composable Named Runnable Stages

The investigation workflow is composed into 7 explicit, named `RunnableLambda` stages executed as a `RunnableSequence`:

1. **`validate_record`**: Checks presence of `recorded_value`, validates numeric parseability via `Decimal`, and verifies supported units (`mm`, `cm`).
2. **`retrieve_eligible_evidence`**: Executes pluggable retrieval (`baseline` or `pgvector`), packages retrieved evidence into standard LangChain `Document` objects with complete provenance metadata, and tracks `retrieval_status` separately in typed workflow state.
3. **`branch_on_retrieval_outcome`**: Inspects retrieval status. Early abstentions (`insufficient_evidence`, `ambiguous_evidence`) or retrieval errors immediately short-circuit to exit responses, ensuring the measurement extractor is **never invoked** when evidence is missing or conflicting.
4. **`extract_measurement`**: Executes the measurement extractor (`deterministic` or `gemini`) exactly once on eligible passages.
5. **`validate_and_align_source_quote`**: Applies strict whitespace-aware quote alignment, attribute name verification, and value/unit grounding checks. Ungrounded or unparseable extractions trigger guardrail failure and return `needs_review` without proposing a correction.
6. **`perform_decimal_conversion_and_comparison`**: Performs deterministic Python `Decimal` conversion and arithmetic comparison (`correction_proposed` vs. `no_change`).
7. **`produce_investigation_response`**: Assembles the structured final response dictionary matching the exact schema contract.

### What LangChain Adds

- **Composable Pipeline**: Explicit stage boundaries using standard LangChain primitives (`RunnableLambda`, `RunnableSequence`).
- **Standard Document Representations**: Packaging retrieved text as `Document(page_content=..., metadata=...)` with document filename, 1-based page number, character offsets, SHA-256 hash, and component ID.
- **Typed State Isolation**: Preserves `retrieval_status` distinctly in workflow state (`ambiguous_evidence` is never converted into an ordinary empty document list).
- **Local Telemetry & Invocation Tracking**: Captures execution duration (ms) and invocation counts for each named stage in `telemetry["stage_metrics"]`. Confirms early abstentions invoke the extractor 0 times and eligible cases invoke it exactly 1 time.
- **Strictly Offline Tracing**: External LangSmith/LangChain tracing is disabled by default (`LANGCHAIN_TRACING_V2=false`, `LANGSMITH_TRACING=false`), requiring zero external API keys or credentials.
- **Exact PgVector Query Plan**: Confirmed using `WITH filtered_chunks AS MATERIALIZED (...)` SQL query plan to guarantee exact cosine distance ranking over the B-tree filtered metadata partition and prevent approximate HNSW index scans from altering rankings.

### 100% Parity Benchmark Across All 16 Cases

Evaluation across the complete 16-case benchmark (10 baseline + 6 challenge cases) demonstrates **100.0% concordance** between direct execution and LangChain execution for both retrievers:

| Suite | Total Cases | Direct Execution Pass Rate | LangChain Orchestration Pass Rate | Concordance Rate |
|---|:---:|:---:|:---:|:---:|
| **Baseline Suite** | 10 | 10/10 (100.0%) | 10/10 (100.0%) | **10/10 (100.0%)** |
| **Challenge Suite** | 6 | 5/6 (83.3%)* | 5/6 (83.3%)* | **6/6 (100.0%)** |
| **Complete Suite (Baseline Retriever)** | 16 | 15/16 (93.8%) | 15/16 (93.8%) | **16/16 (100.0%)** |
| **Complete Suite (PgVector Retriever)** | 16 | 15/16 (93.8%) | 15/16 (93.8%) | **16/16 (100.0%)** |

*\*`challenge-01` fails at deterministic regex extraction due to documented sentence-structure limitation; both direct and LangChain produce identical outputs.*

### Setup & Commands

```bash
# 1. Install optional LangChain orchestration dependencies
pip install -r requirements-orchestration.txt

# 2. Run investigation with LangChain orchestration
python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --orchestration langchain

# 3. Run Step 23 automated verification suite
python3 scripts/verify_step23_langchain.py

# 4. Run baseline evaluation with LangChain
python3 scripts/evaluate.py --extractor deterministic --suite baseline --orchestration langchain
```

---

## 12. Controlled LangGraph Orchestration (Step 24)

In Step 24, an optional **LangGraph StateGraph** orchestration pipeline was implemented (`scripts/investigate_graph.py`), representing the discrepancy investigation as an explicit state machine with guarded conditional transitions and typed tool execution.

### Explicit StateGraph Architecture

The investigation workflow is modeled as a compiled `StateGraph` over a strictly typed `InvestigationGraphState`:

```
validate_record ──[valid]──> retrieve_evidence ──[eligible]──> extract_measurement ──[found]──> validate_evidence ──[pass]──> convert_and_compare ──> finalize
      │                              │                               │                              │                                       ▲
      └──[invalid]───────────────────┴──[insufficient/ambiguous]─────┴──[error/abstain]─────────────┴──[fail]──────────────────────────────────────┘
```

1. **`validate_record`**: Validates input record value presence, Decimal parseability, and supported units (`mm`, `cm`).
   - **Guarded Edge**: If invalid, routes directly to `finalize` (status: `needs_review`).
2. **`retrieve_evidence`**: Executes the typed LangChain tool `evidence_retrieval_tool` (`baseline` or `pgvector`), converting retrieved evidence into standard `Document` objects while tracking `retrieval_status` distinctly.
   - **Guarded Edge**: If retrieval status is `insufficient_evidence`, `ambiguous_evidence`, or `error`, routes directly to `finalize`. The extractor is **never invoked**.
3. **`extract_measurement`**: Executes the typed LangChain tool `measurement_extraction_tool` (`deterministic` or `gemini`) exactly once on eligible passages.
   - **Guarded Edge**: If extraction fails or abstains, routes directly to `finalize`.
4. **`validate_evidence`**: Applies post-extraction guardrails: whitespace-aware quote alignment, attribute name matching, value/unit grounding in cited quote, and supported unit verification.
   - **Guarded Edge**: If guardrails fail (e.g. ungrounded quote, mismatched attribute, or unsupported unit), routes directly to `finalize` (status: `needs_review`).
5. **`convert_and_compare`**: Invoked **strictly after** evidence validation passes. Executes the typed LangChain tool `measurement_conversion_tool` using validated state variables (`validated_ev_val_dec`, `validated_ev_unit_clean`, `record_val_dec`, `record_unit_clean`) to perform exact Python `Decimal` conversion and comparison.
6. **`finalize`**: Assembles the structured final response dictionary satisfying the exact schema contract.

> **Deterministic Control Guarantee**: Tool execution and routing in this graph are **strictly state-guarded and deterministic**, not autonomous LLM tool selection. The graph enforces a finite execution limit (`recursion_limit=10`, max 6 transitions) with zero retry cycles.

### State Isolation, Immutability & Security

- **Strict State Isolation**: Every investigation constructs a completely fresh `InvestigationGraphState` dictionary. No shared mutable state or global counters exist between requests.
- **Credential & Ground Truth Exclusion**: Sensitive credentials (`GEMINI_API_KEY`) and benchmark ground truth answers (`expected_outcome`, `expected_correction`) are strictly excluded from graph state.
- **Isolated Telemetry**: Local node transitions, execution timings (`node_timings`), and tool invocation counts (`tool_invocations`) are captured per run. External LangSmith/LangChain tracing is strictly disabled by default (`LANGCHAIN_TRACING_V2=false`).

### Node Transitions & Execution Traces

| Execution Scenario | Case Example | Visited Node Transitions (Max 6) | Tool Invocations | Extractor Calls | Outcome |
|---|---|---|---|:---:|---|
| **Eligible Discrepancy** | `case-01-correction-cm-to-mm` | `validate_record` → `retrieve_evidence` → `extract_measurement` → `validate_evidence` → `convert_and_compare` → `finalize` (6 nodes) | `evidence_retrieval_tool: 1`<br/>`measurement_extraction_tool: 1`<br/>`measurement_conversion_tool: 1` | 1 | `correction_proposed` (8.0 mm) |
| **Missing Evidence Abstention** | `case-05-unknown-component` | `validate_record` → `retrieve_evidence` → `finalize` (3 nodes) | `evidence_retrieval_tool: 1`<br/>`measurement_extraction_tool: 0`<br/>`measurement_conversion_tool: 0` | 0 | `insufficient_evidence` |
| **Conflicting Evidence Abstention** | `case-08-conflicting-evidence` | `validate_record` → `retrieve_evidence` → `finalize` (3 nodes) | `evidence_retrieval_tool: 1`<br/>`measurement_extraction_tool: 0`<br/>`measurement_conversion_tool: 0` | 0 | `ambiguous_evidence` |
| **Guardrail Rejection (Unsupported Unit)** | `case-09-unsupported-unit` | `validate_record` → `retrieve_evidence` → `extract_measurement` → `validate_evidence` → `finalize` (5 nodes) | `evidence_retrieval_tool: 1`<br/>`measurement_extraction_tool: 1`<br/>`measurement_conversion_tool: 0` | 1 | `needs_review` |
| **Invalid Record Short-Circuit** | `case-10-malformed-measurement` | `validate_record` → `finalize` (2 nodes) | `evidence_retrieval_tool: 0`<br/>`measurement_extraction_tool: 0`<br/>`measurement_conversion_tool: 0` | 0 | `needs_review` |

### 100% 3-Way Parity Across All 16 Benchmark Cases

Evaluation across the complete 16-case benchmark confirms **100.0% concordance** across all three execution engines (`direct`, `langchain`, and `langgraph`) for both `baseline` and `pgvector` retrievers:

| Suite | Total Cases | Direct Execution | LangChain Runnable | LangGraph StateGraph | 3-Way Concordance |
|---|:---:|:---:|:---:|:---:|:---:|
| **Baseline Suite (10 cases)** | 10 | 10 / 10 (100.0%) | 10 / 10 (100.0%) | 10 / 10 (100.0%) | **10 / 10 (100.0%)** |
| **Challenge Suite (6 cases)** | 6 | 5 / 6 (83.3%)* | 5 / 6 (83.3%)* | 5 / 6 (83.3%)* | **6 / 6 (100.0%)** |
| **Complete Suite (Baseline Retriever)** | 16 | 15 / 16 (93.8%) | 15 / 16 (93.8%) | 15 / 16 (93.8%) | **16 / 16 (100.0%)** |
| **Complete Suite (PgVector Retriever)** | 16 | 15 / 16 (93.8%) | 15 / 16 (93.8%) | 15 / 16 (93.8%) | **16 / 16 (100.0%)** |

*\*`challenge-01` represents a documented regex boundary limitation on sentence prose where deterministic extraction abstains safely to `needs_review`.*

### Setup & Commands

```bash
# 1. Install optional orchestration dependencies
pip install -r requirements-orchestration.txt

# 2. Run investigation with LangGraph StateGraph orchestration
python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --orchestration langgraph

# 3. Run Step 24 automated verification suite (9 verification points)
python3 scripts/verify_step24_langgraph.py

# 4. Run baseline evaluation with LangGraph
python3 scripts/evaluate.py --extractor deterministic --suite baseline --orchestration langgraph

# 5. Optional: Configure FastAPI service to use LangGraph orchestration
export INVESTIGATION_ORCHESTRATION=langgraph
uvicorn api.main:app --port 8000
```

---

## 13. Offline vs. Live Workflows

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
| **Database & Vector Storage Verification** | `python3 scripts/verify_step21_database.py` | None | None (local Docker/Postgres) | Yes |
| **Retriever Verification (Step 22)** | `python3 scripts/verify_step22_retrieval.py` | None | None (local Docker/Postgres) | Yes |
| **LangChain Orchestration Verification (Step 23)** | `python3 scripts/verify_step23_langchain.py` | None | None | Yes |
| **LangGraph Orchestration Verification (Step 24)** | `python3 scripts/verify_step24_langgraph.py` | None | None | Yes |
| **Retriever Comparative Benchmark (16 cases)** | `python3 scripts/evaluate.py --retriever both --suite all` | None | None (zero Gemini calls) | Yes |
| **Deterministic Baseline Evaluation (10 cases)** | `python3 scripts/evaluate.py --extractor deterministic --suite baseline` | None | None | Yes |
| **Deterministic Challenge Evaluation (6 cases)** | `python3 scripts/evaluate.py --extractor deterministic --suite challenge` | None | None | Yes |
| **Deterministic Single Investigation** | `python3 scripts/investigate_record.py <record.json> --extractor deterministic` | None | None | Yes |
| **Live Gemini Investigation** | `python3 scripts/investigate_record.py <record.json> --extractor gemini` | `GEMINI_API_KEY` | Yes (1 API call) | No (API transit) |
| **Live Challenge Comparative Benchmark** | `python3 scripts/evaluate.py --extractor both --suite challenge --step 15` | `GEMINI_API_KEY` | Yes (max 6 calls) | No (API transit) |
| **Live Baseline Comparative Benchmark** | `python3 scripts/evaluate.py --extractor both --suite baseline` | `GEMINI_API_KEY` | Yes (max 10 calls) | No (API transit) |
| **Step 25 Final Integrated Verification** | `python3 scripts/verify_step25_integration.py` | `GEMINI_API_KEY` | Yes (exactly 1 API call) | No (Live API integration) |

---

## 14. Evaluation Results & Benchmark Suite

The repository contains two evaluation suites testing length unit mismatches (`cm` ↔ `mm`), agreements, unknown components, incorrect revisions, missing measurements, conflicting evidence, unsupported units, and complex layouts.

### Benchmark Summary

| Evaluation Suite | Suite Size | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Primary Finding |
|---|:---:|:---:|:---:|---|
| **Step 10 Baseline Suite** | 10 cases | **10 / 10 (100.0%)** | **10 / 10 (100.0%)** | Providers showed 100% concordance. In 5 cases, retrieval checks safely abstained prior to model call. |
| **Step 15 Challenge Suite** | 6 cases | 5 / 6 (83.3%) | **6 / 6 (100.0%)** | **Gemini demonstrated value (+16.7 pp)** on unstructured sentence prose (`challenge-01`) where regex rules fail. |
| **Step 22 Retriever Benchmark** | 16 cases | 15 / 16 (93.8%) | N/A (zero Gemini calls) | **100% Concordance between Baseline and PgVector**; 100% Recall@1 (9/9) on gold evidence cases; full safety abstention preservation. |

> **Evaluation Scope & Limitations Notice**: These results are derived from controlled synthetic test suites designed to expose parser boundaries and test pipeline integration. **They do not constitute a benchmark of generalized accuracy across unconstrained, real-world supplier engineering drawings, CAD files, or scanned documents.**

### Key Comparison: Step 22 Retriever Comparative Benchmark (16 Cases)

| Metric | Baseline Retriever | PgVector Retriever | Comparison / Target |
|---|---|---|---|
| **Overall Pass Rate (End-to-End)** | 15 / 16 (93.8%) | 15 / 16 (93.8%) | **100% Concordance (16/16 matches)** |
| **Information Retrieval Recall@1** | 9 / 9 (100.0%) | 9 / 9 (100.0%) | All relevant chunks ranked #1 |
| **Information Retrieval Recall@2** | 9 / 9 (100.0%) | 9 / 9 (100.0%) | All relevant chunks in top 2 |
| **Information Retrieval Recall@3** | 9 / 9 (100.0%) | 9 / 9 (100.0%) | All relevant chunks in top 3 |
| **Mean Reciprocal Rank (MRR)** | 1.000 | 1.000 | Perfect reciprocal ranking |
| **Safety Abstentions Preserved** | 6 / 6 (100.0%) | 6 / 6 (100.0%) | Conflicting & missing evidence safely flagged |
| **Median Investigation Latency** | 0.71 ms | 43.48 ms | Local regex scan vs. CPU embedding + Postgres |

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

### Step 25: Final Integrated End-to-End Verification (LangGraph + PgVector + Live Gemini)

In Step 25, the complete integrated stack was verified end-to-end through the FastAPI HTTP service (`POST /investigations`) with LangGraph state graph orchestration (`INVESTIGATION_ORCHESTRATION=langgraph`), PostgreSQL/pgvector semantic retrieval (`retriever=pgvector`), and live Gemini model extraction (`extractor=gemini`).

> **Integration Scope Notice**: Step 25 is an end-to-end integration and telemetry verification run consisting of **one live positive sample plus one negative abstention check**. It verifies that all components (FastAPI, LangGraph, pgvector, Gemini API, Python Decimal math, and citation guardrails) function cohesively under real network and database conditions. It is **not** a broad accuracy or generalization benchmark (see historical Step 10, 15, and 22 evaluations above for multi-case benchmarks).

#### Environment & System Configuration
- **Host & Runtime**: Darwin arm64 (Python 3.9.6) local; Ubuntu 24.04 (Python 3.13) CI
- **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2` (revision `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384d, normalized)
- **Vector Database**: PostgreSQL 16.10 with pgvector 0.8.0 on localhost:5432
- **Orchestration**: LangGraph 0.6.11 compiled `StateGraph` with 6 explicit nodes and guarded conditional edges
- **LLM Extractor**: `gemini-3.5-flash-lite` via official `google-genai` SDK (retries disabled: `attempts=1`)
- **Live Gemini API Calls**: **Strictly 1 call** across the entire integration step

#### Step 25 HTTP Request Verification Results

| Parameter | Request 1: Positive Sample (`unit-mismatch-001`) | Request 2: Unknown Component (`COMP-NONEXISTENT-999`) |
|---|---|---|
| **Endpoint** | `POST /investigations?retriever=pgvector&extractor=gemini` | `POST /investigations?retriever=pgvector&extractor=gemini` |
| **HTTP Status** | `200 OK` | `200 OK` |
| **Business Outcome** | `correction_proposed` | `insufficient_evidence` (Safe Abstention) |
| **Current Record** | `0.8 mm` (`thickness`) | `5.0 mm` (`thickness`) |
| **Retrieved Evidence** | Chunk `supplier-COMP-001_p1_c003` from `copilot_db` | None (zero matching chunks in `copilot_db`) |
| **Model Extracted Value** | `0.8 cm` (verbatim quote: `"Component thickness: 0.8 cm."`) | N/A (extractor not invoked) |
| **Citation Verification** | Grounded in `supplier-COMP-001.pdf` page 1 | N/A |
| **Proposed Correction** | `8.0 mm` (via Python `Decimal`: `0.8 cm * 10 mm/cm = 8.0 mm`) | `null` (no correction proposed) |
| **LangGraph Path** | `validate_record` → `retrieve_evidence` → `extract_measurement` → `validate_evidence` → `convert_and_compare` → `finalize` (6 nodes) | `validate_record` → `retrieve_evidence` → `finalize` (3 nodes, early exit) |
| **Tool Invocations** | `retrieval: 1`, `extraction: 1`, `conversion: 1` | `retrieval: 1`, `extraction: 0`, `conversion: 0` |
| **Live Gemini Calls** | **1 call** (377 tokens: 323 prompt, 54 candidate, 981.65 ms) | **0 calls** (zero network transit, 38.64 ms total) |
| **Data Immutability** | Records & PDFs verified byte-for-byte unmodified | Records & PDFs verified byte-for-byte unmodified |

### Evaluation Reports
- [evaluation/reports/step25_integration_report.md](evaluation/reports/step25_integration_report.md): Step 25 final integrated RAG verification report (FastAPI + LangGraph + PgVector + Live Gemini).
- [evaluation/reports/step25_integration_report.json](evaluation/reports/step25_integration_report.json): Machine-readable Step 25 integration verification JSON.
- [evaluation/reports/step22_retriever_comparison_report.md](evaluation/reports/step22_retriever_comparison_report.md): Step 22 side-by-side comparative report (Baseline vs. PgVector retrieval on 16 cases).
- [evaluation/reports/step22_retriever_comparison_report.json](evaluation/reports/step22_retriever_comparison_report.json): Machine-readable Step 22 retriever comparison JSON.
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

## 15. Continuous Integration (CI)

An automated GitHub Actions workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) runs on all pushes and pull requests targeting the `main` branch.

### CI Guarantees
1. **Environment Setup**: Provisions Python 3.13 on `ubuntu-latest` and installs dependencies from [`requirements-lock.txt`](requirements-lock.txt).
2. **Data & Text Extraction**: Generates synthetic investigation records and extracts document text page-by-page into `data/extracted/`.
3. **Mock & Schema Validation**: Runs [`scripts/verify_step8_extractor.py`](scripts/verify_step8_extractor.py) verifying Pydantic schema validation, prompt boundaries, and 7 mock scenarios.
4. **Comprehensive Regression Suite**: Runs [`scripts/verify_sample.py`](scripts/verify_sample.py) verifying sample validity, text extraction, retrieval, conversion arithmetic, whitespace quote alignment, labelled tuple binding, immutability, and offline replay.
5. **Offline API & Retriever Tests**: Runs `python -m unittest discover -s tests -p "test_*.py"` verifying API endpoints, verbatim citation-preserving chunking boundaries, document identity safety rejection rules, and retriever factory/mock mechanics.
6. **Deterministic Benchmark Evaluations**:
   - Baseline Suite: Asserts 10/10 expected pass rate (`scripts/evaluate.py --extractor deterministic --suite baseline`).
   - Challenge Suite: Verifies 5/6 expected pass rate (`scripts/evaluate.py --extractor deterministic --suite challenge`), preserving the known `challenge-01` sentence regex limitation while failing if any unexpected regression occurs.
7. **Artifact Archival**: Uploads all generated reports in `evaluation/reports/` as workflow run artifacts.
8. **Zero Credentials**: Runs strictly offline without requiring or accepting `GEMINI_API_KEY`.

---

## 16. Limitations & Scope Boundaries

To maintain reliability, security, and auditability, the project's scope is strictly bounded:

### Controlled State Machine vs. Autonomous LLM Agents
- **Deterministic Tool Invocations**: In both LangChain (`scripts/investigate_chain.py`) and LangGraph (`scripts/investigate_graph.py`), tools are invoked via **state-guarded deterministic code logic**, not autonomous LLM tool selection.
- **Strict Guarded Routing**: Decisions to retrieve, extract, validate, and convert are governed by programmatic condition functions. The LLM does not choose which tools to call or navigate cycles.
- **Finite Graph Execution**: The graph enforces a strict `recursion_limit=10` with zero retry loops; eligible paths complete in at most 6 node transitions, and abstentions complete in 2 to 3 node transitions.

### Evaluation Dataset Scope & Real-World Boundaries
- **Synthetic Test Suites**: All evaluation benchmarks (10 baseline cases, 6 challenge cases, 1 live integration case) are synthetic datasets constructed to test specific edge cases (unit mismatches, revision mismatches, missing values, conflicting statements, multi-column tables).
- **Not an Unconstrained Benchmark**: These results demonstrate pipeline correctness, state guardrails, and deterministic math; **they do not claim generalized accuracy across unconstrained, real-world supplier engineering drawings, scanned blueprints, or complex multi-page CAD specifications.**

### What Is Implemented
- Pluggable evidence retrieval (`--retriever baseline` vs. `--retriever pgvector`) keeping `baseline` as the CLI and API default.
- Pinned query embedding using `sentence-transformers/all-MiniLM-L6-v2` on CPU.
- Parameterized metadata filtering (`corpus_id`, `component_id`, `revision`, `model_name`, `model_revision`) combined with exact cosine ranking and deterministic tie-breaking in PostgreSQL/pgvector.
- Full-context conflict detection across eligible candidate chunks before top-k ranking.
- Citation-preserving chunk spans (`context_type: "chunk"`) grounded in source page text.
- Optional LangChain Runnable pipeline and LangGraph StateGraph orchestration.
- Minimal FastAPI HTTP service (`api/main.py`) exposing `/health` and `/investigations`.

### What Is Not Implemented
- **No OCR for Raster Scans**: Documents must contain selectable digital text (`pypdf` extraction); scanned raster PDFs or image-only drawings are not supported.
- **No Autonomous Tool-Calling Agents**: The investigation workflow is a deterministic, single-turn audit pipeline, not an open-ended conversational agent.
- **No Direct Database Mutation**: The tool generates proposed correction payloads; it does not write directly to production ERP or PLM systems.
- **No Web Frontend UI**: The project exposes a CLI and a minimal FastAPI investigation service (`api/main.py`), but does not provide an interactive frontend web UI.

---

## 17. Portfolio MVP Completion Status

With the successful completion of **Step 25**, this repository has achieved full portfolio MVP status:
- **Verified Offline Core**: Reproducible environment, deterministic baseline extractor, PDF text extraction, citation-preserving chunking, Python `Decimal` arithmetic, and comprehensive automated regression suites.
- **Semantic Retrieval Layer**: Local containerized PostgreSQL 16 with `pgvector`, B-tree metadata filtering, exact cosine distance ranking, and evaluation corpora indexing.
- **Production Orchestration**: Modular, zero-dependency direct execution alongside optional LangChain Runnable and LangGraph StateGraph orchestration with 100% parity across all 16 benchmark cases.
- **Live LLM Integration**: Controlled, schema-enforced `gemini-3.5-flash-lite` extraction with post-extraction quote grounding, zero LLM math, and strict API call budgeting.
- **Service API**: FastAPI HTTP microservice exposing health and investigation endpoints with comprehensive telemetry.
- **Continuous Integration**: Automated GitHub Actions CI pipeline running offline checks on Python 3.13.

---

## 18. Project Documentation

- [docs/DEMO.md](docs/DEMO.md): Interactive CLI walkthrough and interview demonstration guide.
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): Complete project brief, problem definition, scope, JSON schemas, evaluation criteria, and deferred features.
- [docs/PROGRESS.md](docs/PROGRESS.md): Step-by-step progress tracking, verification logs, and milestone history.
