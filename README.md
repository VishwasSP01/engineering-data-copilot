# Engineering Data Copilot

An AI assistant that investigates engineering data-quality issues using documents and evidence.

## Overview
Engineering Data Copilot audits engineering records (such as component dimensions and tolerances) against authoritative supplier technical documentation (such as supplier datasheet PDFs). It identifies discrepancies—specifically measurement-unit mismatches—and proposes evidence-backed corrections verified by deterministic arithmetic.

## Setup

Create and activate a local virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
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

### Live Gemini Prerequisites & Status
To use the Gemini extractor in live environments:
1. Set the API key environment variable:
   ```bash
   export GEMINI_API_KEY="your-api-key"
   ```
2. (Optional) Set the target Gemini model:
   ```bash
   export GEMINI_MODEL="gemini-2.5-flash"
   ```

> **Notice on Live Gemini Verification**: Automated tests and verification suites operate entirely offline using injected mock clients with simulated responses. **Live Gemini behavior against the production API has not yet been verified.** Do not rely on live model calls without verifying connectivity, latency, and quotas in your deployment environment.

## Verification

To run the complete verification suite across all steps (sample validity, text extraction, deterministic retrieval, correction logic, benchmark evaluation, and Step 8 mock extractor guardrails):

```bash
python3 scripts/verify_sample.py
```

To run Step 8 extractor tests directly:

```bash
python3 scripts/verify_step8_extractor.py
```

## Evaluation

To run the synthetic evaluation suite across 10 benchmark cases (testing corrections in both directions, agreements, unknown components, incorrect revisions, missing measurements, conflicting evidence, unsupported units, and malformed inputs):

```bash
python3 scripts/evaluate.py
```

Generated reports:
- [evaluation/reports/evaluation_report.md](evaluation/reports/evaluation_report.md): Human-readable Markdown summary with per-case results, latency metrics, and citation checks.
- [evaluation/reports/evaluation_report.json](evaluation/reports/evaluation_report.json): Machine-readable JSON evaluation report.

> **Notice**: This benchmark tests deterministic pipeline behavior across a small synthetic dataset. It does not claim to demonstrate production accuracy.

## Documentation
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): Complete project brief, problem definition, scope, JSON schemas, evaluation criteria, and deferred features.
- [docs/PROGRESS.md](docs/PROGRESS.md): Step-by-step progress tracking and verification log.
