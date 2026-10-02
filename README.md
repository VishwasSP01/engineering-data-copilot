# Engineering Data Copilot

An AI assistant that investigates engineering data-quality issues using documents and evidence.

## Overview
Engineering Data Copilot audits engineering records (such as component dimensions and tolerances) against authoritative supplier technical documentation (such as supplier datasheet PDFs). It identifies discrepancies—specifically measurement-unit mismatches—and proposes evidence-backed corrections verified by deterministic arithmetic.

## Setup

### Supported Environment
- **Python**: Python 3.9+ (tested on Python 3.9.6).
- **OS**: macOS, Linux, Windows.

### Fresh Checkout Quickstart

1. **Clone the repository**:
   ```bash
   git clone https://github.com/VishwasSP01/engineering-data-copilot.git
   cd engineering-data-copilot
   ```

2. **Create and activate a virtual environment**:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

3. **Install dependencies**:
   To install the exact reproducible dependency lock (including transitive dependencies):
   ```bash
   pip install -r requirements-lock.txt
   ```
   *(Alternatively, install package ranges using `pip install -r requirements.txt`)*

4. **Prepare synthetic data and extracted text**:
   `data/extracted/` is gitignored to avoid committing regenerable derivative text. Generate sample artifacts and extract document text:
   ```bash
   python3 scripts/generate_sample.py
   python3 scripts/extract_documents.py
   ```

## Offline vs. Live Workflows

The repository strictly separates zero-cost, offline verification from live model evaluations requiring credentials.

### Offline Workflows (Zero Credentials, Zero Network, Zero API Cost)
All regression suites, baseline deterministic evaluations, and unit tests run entirely offline:
- **Comprehensive Offline Verification (Steps 3–14)**:
  ```bash
  python3 scripts/verify_sample.py
  ```
- **Step 8 Mock Extractor & Guardrail Checks**:
  ```bash
  python3 scripts/verify_step8_extractor.py
  ```
- **Deterministic Baseline Evaluation (10 Cases - Expected: 10/10)**:
  ```bash
  python3 scripts/evaluate.py --extractor deterministic --suite baseline
  ```
- **Deterministic Challenge Evaluation (6 Cases - Expected: 5/6, Documented Sentence Regex Limitation)**:
  ```bash
  python3 scripts/evaluate.py --extractor deterministic --suite challenge
  ```
- **Single Deterministic Investigation**:
  ```bash
  python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor deterministic
  ```

### Live Workflows (Requires `GEMINI_API_KEY`)
Live Gemini calls require API credentials in `.env` (kept strictly gitignored) or shell environment:
- **Single Record Investigation with Live Gemini**:
  ```bash
  python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor gemini
  ```
- **Live Challenge Comparison (Step 15)**:
  ```bash
  python3 scripts/evaluate.py --extractor both --suite challenge --step 15
  ```
- **Live Baseline Comparison (Step 10)**:
  ```bash
  python3 scripts/evaluate.py --extractor both --suite baseline
  ```

## Synthetic Data Generation

To generate the reproducible synthetic investigation sample (`unit-mismatch-001`):

```bash
python3 scripts/generate_sample.py
```

This generates:
- `data/records/unit-mismatch-001.json`: The engineering database record containing a unit mismatch (`thickness: 0.8 mm`).
- `data/documents/supplier-COMP-001.pdf`: Single-page synthetic supplier datasheet with authoritative measurement (`Component thickness: 0.8 cm.`).
- `evaluation/expected/unit-mismatch-001.json`: Evaluation benchmark file containing the expected correction (`8.0 mm`) and exact evidence citations.

## Document Text Extraction

To extract text page-by-page from supplier PDF documents in `data/documents/` while preserving citation information:

```bash
python3 scripts/extract_documents.py
```

This generates:
- `data/extracted/<document_name>.json`: Page-by-page extracted text preserving `source_file` and 1-indexed `page_number`. Unreadable files or pages without extractable text are explicitly caught and reported.

## Evidence Retrieval

To retrieve evidence passages for an engineering record from extracted documents using deterministic baseline matching:

```bash
python3 scripts/retrieve_evidence.py data/records/unit-mismatch-001.json
```

Example output:

```json
{
  "record_id": "unit-mismatch-001",
  "component_id": "COMP-001",
  "revision": "A",
  "attribute_name": "thickness",
  "status": "evidence_found",
  "retrieval_status": "evidence_found",
  "document_filename": "supplier-COMP-001.pdf",
  "page_number": 1,
  "evidence_passage": "Component thickness: 0.8 cm.",
  "evidence": {
    "document_filename": "supplier-COMP-001.pdf",
    "page_number": 1,
    "supporting_passage": "Component thickness: 0.8 cm."
  },
  "reason": "Found unambiguous measurement passage on page 1 of supplier-COMP-001.pdf."
}
```

## Record Investigation & Correction Proposal

To run an end-to-end investigation for an engineering record (record input → evidence retrieval → unit conversion → exact comparison → proposal):

```bash
python3 scripts/investigate_record.py data/records/unit-mismatch-001.json
```

Example output:

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
    "model": null,
    "mode": "deterministic",
    "is_fallback": false,
    "call_duration_ms": 0.12,
    "token_usage": null,
    "token_usage_reason": "Token usage not applicable for deterministic extractor."
  },
  "explanation": "Supplier document specifies 0.8 cm, which converts via deterministic arithmetic to 8.0 mm (0.8 cm * 10 mm/cm = 8.0 mm). Recorded value is 0.8 mm. Proposing correction to 8.0 mm."
}
```

## Measurement Extractors (Deterministic vs Gemini)

The investigation workflow supports pluggable measurement extractors via the `--extractor` CLI flag:

- `--extractor deterministic` (default): Fast, deterministic regex extraction.
- `--extractor gemini`: Structured model extraction via the official `google-genai` SDK (`gemini-2.5-flash`).

```bash
# Run with Gemini extractor (requires GEMINI_API_KEY environment variable)
python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor gemini
```

### Post-Extraction Verification Guardrails
Regardless of extractor used, all extractions must pass strict deterministic verification before being fed into conversion logic:
1. **Pydantic Schema Validation**: The response must conform to `MeasurementExtractionResponse` (`status`, `measurement_name`, `value` as decimal string, `unit`, `quote`).
2. **Quote Grounding**: The supporting `quote` must exist verbatim in the retrieved evidence passage. Ungrounded or hallucinated quotes trigger `needs_review`.
3. **Attribute Alignment**: The extracted measurement attribute must match the requested engineering record attribute.
4. **Value & Unit Grounding**: The extracted numeric value and unit must be present within the cited supporting quote.
5. **Supported Units**: Only length units `mm` and `cm` are supported.
6. **Deterministic Math**: Conversion arithmetic is strictly performed using Python `Decimal` arithmetic. The model is never asked to calculate conversions or propose corrections.

### Live Gemini Configuration & Status
To use the Gemini extractor in live environments:
1. Provide your API key via `.env` file in the repository root or via shell environment:
   ```bash
   GEMINI_API_KEY="your-api-key"
   GEMINI_MODEL="gemini-3.5-flash-lite"
   ```
2. Run investigation with `--extractor gemini`:
   ```bash
   python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor gemini
   ```

> **Notice on Live Gemini Verification**: Live Gemini model extraction has been verified on a single reproducible synthetic sample (`unit-mismatch-001`) using `gemini-3.5-flash-lite` (see [evaluation/reports/live_investigation_report.md](evaluation/reports/live_investigation_report.md)). **This single-sample run demonstrates technical feasibility and pipeline integration; it does not constitute a statistical accuracy or performance benchmark across varied real-world engineering documents.** Automated evaluation suites and regression tests run entirely offline via injected mock clients to ensure deterministic, zero-cost verification.

## Verification

To run the complete verification suite across all steps (sample validity, text extraction, deterministic retrieval, correction logic, benchmark evaluation, and Step 8 mock extractor guardrails):

```bash
python3 scripts/verify_sample.py
```

To run Step 8 extractor tests directly:

```bash
python3 scripts/verify_step8_extractor.py
```

## Evaluation & Benchmark Suite

The repository contains an isolated 10-case synthetic benchmark suite testing length unit mismatches (`cm` ↔ `mm`), agreements, unknown components, incorrect revisions, missing measurements, conflicting evidence, unsupported units, and malformed inputs.

### Running the Evaluator
```bash
# Run deterministic baseline evaluation (default)
python3 scripts/evaluate.py --extractor deterministic

# Run live Gemini evaluation
python3 scripts/evaluate.py --extractor gemini

# Run comparative evaluation between both providers
python3 scripts/evaluate.py --extractor both
```

### Step 10 Comparative Results (10 Baseline Synthetic Cases)

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) |
|---|---|---|
| **Overall Pass Rate** | 10 / 10 (100.0%) | 10 / 10 (100.0%) |
| **Correction Cases** | 2 / 2 (100.0%) | 2 / 2 (100.0%) |
| **Agreement Cases (`no_change`)** | 2 / 2 (100.0%) | 2 / 2 (100.0%) |
| **Abstention Cases** | 6 / 6 (100.0%) | 6 / 6 (100.0%) |
| **Citation Validity** | 5 / 5 (100.0%) | 5 / 5 (100.0%) |
| **Model Requests** | 0 | 5 attempted / 5 succeeded |
| **Early Abstention (No Call)** | 10 / 10 (100.0%) | 5 / 10 (50.0%) |
| **Median Latency (All 10 Cases)** | 0.63 ms | 381.38 ms |
| **Median Latency (Model-Called, 5 Cases)** | 0.84 ms | 791.92 ms |
| **Median Latency (Non-Model, 5 Cases)** | 0.57 ms | 0.32 ms |
| **Token Usage** | 0 tokens | 1,241 total tokens |
| **Estimated Cost** | $0.00 | null (unestimated) |
| **Concordance** | — | **10 / 10 (100.0% match)** |

> **Limitations & Scope Notice**: Live `gemini-3.5-flash-lite` **matched** the deterministic baseline across all 10 synthetic test cases without improving or degrading decision quality. In 5 cases, retrieval or input checks safely abstained prior to model invocation. **All findings are strictly limited to these synthetic fixtures and do not claim to demonstrate generalization or accuracy on complex real-world engineering drawings or tables.**

### Step 11 & 12 Challenge Suite (Varied Datasheet Layouts & Improved Retrieval)

Step 11 established a 6-case challenge suite designed to expose limitations of the baseline when datasheet phrasing and formatting vary. Step 12 decoupled evidence retrieval from measurement parsing, adding verbatim section/page fallback with `context_type` provenance (`passage`, `section`, `page`).

```bash
# Run deterministic workflow against the 6 challenge cases
python3 scripts/evaluate.py --suite challenge
```

| Challenge Case ID | Description / Layout Variation | Expected Outcome | Actual Outcome | Retrieval | Cit. Valid | Result | Failure Stage |
|---|---|---|---|---|---|---|---|
| `challenge-01-complete-sentence` | Thickness stated in complete sentence | `correction_proposed` | `needs_review` | ✓ (section) | ✓ | **FAIL** | Measurement extraction (interstitial prose `COMP-C01 is`) |
| `challenge-02-table-value-unit-columns` | Separate parameter, value, and unit table columns | `correction_proposed` | `correction_proposed` | ✓ (section) | ✓ | **PASS** | — (Parsed 15.0 mm -> proposed 1.5 cm) |
| `challenge-03-split-lines-label-measurement` | Label and measurement wrapped across line break | `correction_proposed` | `correction_proposed` | ✓ (section) | ✓ | **PASS** | — (Parsed 2.4 mm -> proposed 0.24 cm) |
| `challenge-04-distracting-measurements` | Thickness alongside concatenated length and width | `no_change` | `no_change` | ✓ (section) | ✓ | **PASS** | — (Labelled tuple parsed 6.0 mm -> no_change) |
| `challenge-05-incorrect-revision` | Correct component ID but incorrect Revision B | `insufficient_evidence` | `insufficient_evidence` | ✓ (abstained) | ✓ | **PASS** | — (Revision guardrail confirmed) |
| `challenge-06-conflicting-statements` | Two conflicting thickness values in document | `ambiguous_evidence` | `ambiguous_evidence` | ✓ (abstained) | ✓ | **PASS** | — (Ambiguity guardrail confirmed) |

- **Evidence Retrieval Success Rate**: **4 / 4 (100.0%)** on cases expecting evidence.
- **Retrieval Abstention Success Rate**: **2 / 2 (100.0%)** on missing/conflicting cases.
- **Combined Retrieval Accuracy**: **6 / 6 (100.0%)**.
- **End-to-End Pass Rate**: **5 / 6 (83.3%)** (an increase of 16.7 percentage points from 4 / 6 in Step 12, and 50.0 percentage points from 2 / 6 in Step 11).
- **Remaining Deterministic Limitations**: Only `challenge-01` remains failing deterministically at `measurement extraction`, where regex cannot parse interstitial sentence prose.

### Step 14: Quote Alignment and Measurement Binding

Step 14 addressed the findings from Step 13 without making live Gemini calls:
1. **Whitespace-Aware Quote Alignment (`align_quote_to_passage`)**: Preserves strict literal matching as primary check; falls back to token index mapping for whitespace/line-break variations (e.g. `challenge-01`). Returns the original verbatim contiguous source span as citation, retaining the model quote for audit. Strictly rejects modified numbers, units, invented words, or ambiguities.
2. **Deterministic Labelled Tuple Binding (`parse_labelled_tuple`)**: Positionally binds multi-dimension tuples (e.g. `(length, width, thickness): 60 mm x 40 mm x 6 mm`) to requested attributes, resolving `challenge-04` deterministically. Safely abstains if correspondence is unclear.
3. **Replay Validation**: Validated the saved Step 13 `challenge-01` Gemini extraction offline through quote alignment and deterministic Decimal arithmetic (`1.2 cm` -> `12.0 mm`), confirming exact agreement with expected answer.

### Step 13 Comparative Results (Challenge Suite: Varied Datasheets)

Following Step 12's retrieval improvement, Step 13 compared the deterministic regex baseline against live `gemini-3.5-flash-lite` across the 6 challenging datasheets to determine whether model extraction adds value when sufficient evidence reaches the extractor.

```bash
# Run comparative challenge evaluation between deterministic and live Gemini
python3 scripts/evaluate.py --extractor both --suite challenge
```

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Comparison |
|---|---|---|---|
| **Overall Pass Rate (End-to-End)** | 4 / 6 (66.7%) | **5 / 6 (83.3%)** | **Gemini Improved (+16.6%)** |
| **Retrieval Success Rate** | 6 / 6 (100.0%) | 6 / 6 (100.0%) | Identical |
| **Correction Cases** | 2 / 3 (66.7%) | 2 / 3 (66.7%) | Identical |
| **Agreement Cases (`no_change`)** | 0 / 1 (0.0%) | **1 / 1 (100.0%)** | Gemini Higher |
| **Abstention Cases** | 2 / 2 (100.0%) | 2 / 2 (100.0%) | Identical |
| **Citation Validity** | 4 / 4 (100.0%) | 4 / 4 (100.0%) | Identical |
| **Model Requests** | 0 | 4 attempted / 4 completed | 2 safely skipped (retrieval abstention) |
| **Median Latency (All 6 Cases)** | 0.46 ms | 821.71 ms | Deterministic is faster |
| **Median Latency (Model-Called, 4 Cases)** | N/A | 872.17 ms | Network API transit |
| **Median Latency (Non-Model, 2 Cases)** | 0.46 ms | 0.43 ms | Local early abstention |
| **Token Usage** | 0 tokens | 1,395 total tokens (1,142 prompt, 253 candidate) | — |
| **Estimated Cost** | $0.00 | null (unestimated) | Pricing external to API metadata |
| **Provider Concordance** | — | **5 / 6 (83.3%)** | — |

**Key Step 13 Findings**:
- **Measurable Value-Add**: Gemini resolved the multi-dimension disambiguation limitation on `challenge-04-distracting-measurements` (`"Package dimensions (length, width, thickness): 60.0 mm x 40.0 mm x 6.0 mm."`), correctly identifying thickness as `6.0 mm` (0.6 cm) and proposing `no_change` where the deterministic regex greedily grabbed `60.0 mm`.
- **Zero Regressions**: Gemini matched deterministic performance on table columns (`challenge-02`), split lines (`challenge-03`), revision mismatch (`challenge-05`), and ambiguity (`challenge-06`).
- **Validation Rejection of Potentially Correct Extraction (`challenge-01`)**: On `challenge-01-complete-sentence`, Gemini correctly identified `1.2 cm`, but normalized a newline in `"is\nmanufactured"` to a single space `"is manufactured"`. Downstream Guardrail 1 rejected the quote as non-verbatim (`needs_review`). Validation was kept strict without code alterations, correctly categorized as a `validation` failure.
- **Safety Preservation**: Early abstention on revision mismatch and conflicting evidence prevented 2 unnecessary model invocations (saving 33.3% of model calls).

### Step 15 Live Comparative Evaluation (Challenge Suite)

Following Step 14's evidence validation enhancements (whitespace-aware quote alignment and labelled tuple binding), Step 15 re-evaluated live `gemini-3.5-flash-lite` against the deterministic baseline on the 6 challenge cases under frozen versions (`cfcbbda5b5df1a915a2e074caf015a3fbd34f4be`).

```bash
# Run comparative challenge evaluation with Step 15 reporting
python3 scripts/evaluate.py --extractor both --suite challenge --step 15
```

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Comparison |
|---|---|---|---|
| **Overall Pass Rate (End-to-End)** | 5 / 6 (83.3%) | **6 / 6 (100.0%)** | **Gemini Higher (+16.7 percentage points)** |
| **Evidence Retrieval Success Rate** | 4 / 4 (100.0%) | 4 / 4 (100.0%) | Identical |
| **Retrieval Abstention Success Rate** | 2 / 2 (100.0%) | 2 / 2 (100.0%) | Identical |
| **Combined Retrieval Accuracy** | 6 / 6 (100.0%) | 6 / 6 (100.0%) | Identical |
| **Correction Cases** | 2 / 3 (66.7%) | **3 / 3 (100.0%)** | Gemini Higher |
| **Agreement Cases (`no_change`)** | 1 / 1 (100.0%) | 1 / 1 (100.0%) | Identical |
| **Abstention Cases** | 2 / 2 (100.0%) | 2 / 2 (100.0%) | Identical |
| **Citation Validity** | 4 / 4 (100.0%) | 4 / 4 (100.0%) | Identical |
| **Model Requests Attempted** | 0 / 6 | 4 / 6 | Max 6 budget preserved |
| **Model Requests Completed** | 0 / 0 | 4 / 4 | 100.0% completion, zero retries |
| **Cases Without Model Call (Skipped)** | 6 / 6 (100.0%) | 2 / 6 (33.3%) | Retrieval early abstention |
| **Median Latency (All 6 Cases)** | 0.48 ms | 813.33 ms | Deterministic is faster |
| **Median Latency (Model-Called, 4 Cases)** | N/A | 880.62 ms | Network API transit |
| **Median Latency (Non-Model, 2 Cases)** | 0.48 ms | 0.23 ms | Local early abstention |
| **Token Usage** | 0 tokens | 1,395 total tokens (1,142 prompt, 253 candidate) | Across 4 live calls |
| **Estimated Cost** | $0.00 | null (unestimated) | Pricing external to API metadata |
| **Provider Concordance** | — | **5 / 6 (83.3%)** | — |

**Evolution Across Challenge Milestones**:
| Milestone | Mode | Deterministic Pass Rate | Gemini Pass Rate | `challenge-01` (Sentence) | `challenge-04` (Tuple) | Key Finding |
|---|---|---|---|---|---|---|
| **Step 13** | Live API Call | 4 / 6 (66.7%) | 5 / 6 (83.3%) | Gemini FAIL (newline mismatch) | Gemini PASS (`no_change`) | Gemini resolved tuple disambiguation; newline in sentence triggered strict verbatim rejection |
| **Step 14** | Offline Replay | 5 / 6 (83.3%) | 6 / 6 (100.0%) [Replay] | Replay PASS (whitespace mapped) | Det PASS (tuple parsed) | Token index mapping aligned quote offline; labelled tuple parsed deterministically |
| **Step 15** | Live API Call | 5 / 6 (83.3%) | **6 / 6 (100.0%)** | **Gemini PASS (live)** | **Gemini PASS (live)** | Live validation confirmed end-to-end; whitespace alignment resolved `challenge-01` live |

**Key Step 15 Takeaways**:
- **Full Challenge Suite Pass (100.0%)**: With whitespace-aware quote alignment active, Gemini cleanly aligned the supporting quote for `challenge-01-complete-sentence` across the source PDF line-break, converting `1.2 cm` via Decimal arithmetic to `12.0 mm` and proposing correction. The deterministic regex remains unable to parse interstitial sentence prose.
- **Efficiency via Early Abstention**: 2 of the 6 cases (`challenge-05` and `challenge-06`) were aborted during retrieval without invoking the model, saving 33.3% of API requests and running in 0.23 ms.
- **Zero Hallucination or Conversion Drift**: All candidate responses passed Pydantic schema validation, quote grounding, and attribute alignment; conversions strictly utilized Python `Decimal`.

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

## Continuous Integration (CI)

A GitHub Actions workflow ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) automatically runs on all pushes and pull requests targeting the `main` branch.

### CI Guarantees & Pipeline Steps
1. **Environment Setup**: Provisions Python 3.9 on `ubuntu-latest` and installs dependencies from [`requirements-lock.txt`](requirements-lock.txt).
2. **Data & Text Extraction**: Generates synthetic investigation records and extracts document text page-by-page into `data/extracted/`.
3. **Step 8 Mock Extractor Suite**: Runs [`scripts/verify_step8_extractor.py`](scripts/verify_step8_extractor.py) verifying Pydantic schema validation, prompt boundaries, and 7 mock scenarios offline.
4. **Comprehensive Regression Suite**: Runs [`scripts/verify_sample.py`](scripts/verify_sample.py) verifying sample validity, text extraction, retrieval, conversion arithmetic, whitespace quote alignment, labelled tuple binding, immutability, and offline replay.
5. **Deterministic Benchmark Evaluations**:
   - Baseline Suite: Asserts 10/10 expected pass rate (`scripts/evaluate.py --extractor deterministic --suite baseline`).
   - Challenge Suite: Verifies 5/6 expected pass rate (`scripts/evaluate.py --extractor deterministic --suite challenge`), preserving the known `challenge-01` sentence regex limitation while failing if any unexpected regression occurs.
6. **Report Archival**: Saves all generated evaluation reports from `evaluation/reports/` as workflow artifacts.
7. **Zero Network & Secret Safety**: Runs strictly offline without requiring or accepting `GEMINI_API_KEY` credentials.

## Documentation
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): Complete project brief, problem definition, scope, JSON schemas, evaluation criteria, and deferred features.
- [docs/PROGRESS.md](docs/PROGRESS.md): Step-by-step progress tracking and verification log.

