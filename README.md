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

## Verification

To run the verification suite and confirm that all artifacts are valid, identifiers and revisions match, PDF content and selectable text are present, and deterministic arithmetic is correct:

```bash
python3 scripts/verify_sample.py
```

## Documentation
- [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md): Complete project brief, problem definition, scope, JSON schemas, evaluation criteria, and deferred features.
- [docs/PROGRESS.md](docs/PROGRESS.md): Step-by-step progress tracking and verification log.
