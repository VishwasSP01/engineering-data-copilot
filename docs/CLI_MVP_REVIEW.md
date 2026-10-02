# CLI Portfolio MVP Review & Final Verification

This document records the comprehensive review and independent verification of the **Engineering Data Copilot** CLI Portfolio MVP at Step 18. It verifies that a new reviewer can follow the documentation from scratch, execute offline verification and demo workflows, and understand the project's measured capabilities and strict architectural guardrails.

---

## 1. Executive Summary & Milestone Status

- **Milestone**: Step 18 — Final Review of the CLI Portfolio MVP.
- **Status**: **COMPLETE & VERIFIED**.
- **Scope**: Fully functional, reproducible CLI engineering data investigation tool with dual extraction (deterministic regex and live Google Gemini), strict quote grounding, Python `Decimal` conversion arithmetic, and automated regression-proof CI.
- **Zero-Network / Zero-Call Verification**: Confirmed that **no Gemini API calls occur during offline verification**. Dependency installation from PyPI and GitHub Actions runner setup use network access, but all verification tests, mock suites, and deterministic evaluations run 100% offline.

---

## 2. Reviewed Commit & Tested Environments

- **Reviewed Commit**: [`7851531`](https://github.com/VishwasSP01/engineering-data-copilot/commit/7851531) (`"Prepare CLI demo and portfolio documentation"`).
- **Local Tested Environment**: macOS (Darwin arm64) with **Python 3.9.6**.
- **Remote CI Environment**: Linux (`ubuntu-latest` / Ubuntu 24.04 x86_64) with **Python 3.13** via automated GitHub Actions ([Run 36985686339](https://github.com/VishwasSP01/engineering-data-copilot/actions/runs/36985686339)).
- **Clean Checkout Verification**: Executed in a completely isolated scratch checkout (`review_checkout`) cloned directly from `https://github.com/VishwasSP01/engineering-data-copilot.git` without copying `.env`, `.venv`, or `data/extracted/`.

---

## 3. Quickstart Verification & Command Audit

The quickstart instructions in [`README.md`](../README.md) were followed step-by-step in the clean checkout:

| Step | Command Executed | Actual Result | Verification Status |
|---|---|---|:---:|
| 1. Create Virtualenv | `python3 -m venv .venv` | Isolated virtual environment created | ✓ PASS |
| 2. Install Dependencies | `pip install -r requirements-lock.txt` | All 27 pinned direct and transitive dependencies installed without conflicts | ✓ PASS |
| 3. Generate Sample Data | `python3 scripts/generate_sample.py` | Generated record JSON, PDF datasheet, and expected evaluation fixture | ✓ PASS |
| 4. Extract Documents | `python3 scripts/extract_documents.py` | Extracted selectable text page-by-page into `data/extracted/` | ✓ PASS |
| 5. Offline Verification Suite | `python3 scripts/verify_sample.py` | All Steps 3–14 verification checks passed (sample validity, extraction, retrieval, conversion, quote alignment, tuple binding, immutability) | ✓ PASS |
| 6. Mock Extractor Suite | `python3 scripts/verify_step8_extractor.py` | Passed all 7 mock scenarios (schema validation, prompt boundaries, quote grounding, unit guardrails, timeouts, missing credentials) | ✓ PASS |
| 7. Baseline Evaluation | `python3 scripts/evaluate.py --extractor deterministic --suite baseline` | 10 / 10 passed (100.0%), median latency 0.47 ms | ✓ PASS |
| 8. Challenge Evaluation | `python3 scripts/evaluate.py --extractor deterministic --suite challenge` | 5 / 6 passed (83.3%), median latency 0.49 ms, preserved `challenge-01` sentence regex limitation | ✓ PASS |

---

## 4. Offline Demo Walkthrough Execution

Executed all offline demo commands documented in [`docs/DEMO.md`](DEMO.md):

### Scenario 1: Supported Discrepancy Correction (`unit-mismatch-001`)
- **Command**:
  ```bash
  python3 scripts/investigate_record.py data/records/unit-mismatch-001.json --extractor deterministic
  ```
- **Outcome**: `correction_proposed`
- **Correction**: `8.0 mm` from `0.8 cm` datasheet evidence using Python `Decimal` arithmetic (`0.8 cm * 10 mm/cm = 8.0 mm`).
- **Citation**: `supplier-COMP-001.pdf`, page 1, exact quote `"Component thickness: 0.8 cm."`.
- **Immutability**: Source record was not modified (`"source_record_modified": false`).

### Scenario 2A: Conflicting Evidence Abstention (`case-08-conflicting-evidence`)
- **Command**:
  ```bash
  python3 scripts/investigate_record.py evaluation/cases/case-08-conflicting-evidence/record.json \
    --extracted-dir evaluation/cases/case-08-conflicting-evidence/extracted
  ```
- **Outcome**: `ambiguous_evidence`, `"proposed_correction": null`.
- **Safety**: Extractor was never invoked (`"token_usage_reason": "Retrieval yielded ambiguous_evidence; extractor not invoked."`).

### Scenario 2B: Revision Mismatch Abstention (`challenge-05-incorrect-revision`)
- **Command**:
  ```bash
  python3 scripts/investigate_record.py evaluation/cases/challenge-05-incorrect-revision/record.json \
    --extracted-dir evaluation/cases/challenge-05-incorrect-revision/extracted
  ```
- **Outcome**: `insufficient_evidence`, `"proposed_correction": null`.
- **Safety**: Extractor was never invoked (`"token_usage_reason": "Retrieval yielded insufficient_evidence; extractor not invoked."`).

### Scenario 3: Demonstrated Model Value-Add (`challenge-01-complete-sentence`)
- **Deterministic Baseline**:
  ```bash
  python3 scripts/investigate_record.py evaluation/cases/challenge-01-complete-sentence/record.json \
    --extracted-dir evaluation/cases/challenge-01-complete-sentence/extracted \
    --extractor deterministic
  ```
  - **Outcome**: `needs_review` (`"Evidence unit 'is' is unsupported"`). Regex fails on interstitial prose `"is manufactured to"`.
- **Historical Live Gemini Result (Step 15)**:
  - Extracted `"1.2 cm"` with supporting quote.
  - Aligned across PDF line break (`"is\nmanufactured"`) via `align_quote_to_passage`.
  - Python `Decimal` calculated `1.2 cm * 10 = 12.0 mm`, proposing correction to `12.0 mm` (**PASS**).

---

## 5. Security & Decoupling Audit

1. **Decoupling from Expected Answers**:
   - Confirmed via static analysis that runtime investigation code ([`scripts/retrieve_evidence.py`](../scripts/retrieve_evidence.py), [`scripts/investigate_record.py`](../scripts/investigate_record.py), [`scripts/extractors.py`](../scripts/extractors.py)) **never imports or reads `evaluation/expected/`**.
   - Expected answers are accessed solely by evaluation harnesses ([`scripts/evaluate.py`](../scripts/evaluate.py), [`scripts/verify_sample.py`](../scripts/verify_sample.py)).
2. **Credential Exclusion**:
   - Confirmed `.env` and `.env.*` are strictly ignored by [`.gitignore`](../.gitignore) and untracked by Git.
   - No credentials or API keys exist in commits, diffs, or logs.
3. **Artifact Hygiene**:
   - `data/extracted/` and virtual environments (`.venv/`) are untracked and excluded from git tracking.
4. **Source Immutability**:
   - Verified across all cases that database records and source PDF documents are never overwritten or mutated during investigation.

---

## 6. Links to Historical Live Reports & Verified CI Runs

- **GitHub Actions CI (Python 3.13)**: [Run 36985686339](https://github.com/VishwasSP01/engineering-data-copilot/actions/runs/36985686339) (`Conclusion: success`).
- **Step 15 Challenge Comparison**: [Markdown Report](../evaluation/reports/step15_challenge_comparison_report.md) | [JSON Report](../evaluation/reports/step15_challenge_comparison_report.json).
- **Step 13 Challenge Comparison**: [Markdown Report](../evaluation/reports/challenge_comparison_report.md) | [JSON Report](../evaluation/reports/challenge_comparison_report.json).
- **Step 10 Baseline Comparison**: [Markdown Report](../evaluation/reports/comparison_report.md) | [JSON Report](../evaluation/reports/comparison_report.json).
- **Step 9 Single Live Investigation**: [Markdown Report](../evaluation/reports/live_investigation_report.md) | [JSON Report](../evaluation/reports/live_investigation_report.json).

---

## 7. Known Limitations & Honest Scope

- **Evaluation Scope**: All performance and accuracy numbers are derived from small synthetic test suites (10 baseline cases, 6 challenge cases) designed to test pipeline boundaries. **They do not constitute a benchmark of generalized accuracy across unconstrained production engineering drawings, CAD files, or scanned documents.**
- **Deterministic Regex Limits**: The deterministic extractor relies on standard label patterns and explicit dimension tuples; it fails on complex interstitial sentences (e.g. `challenge-01`).
- **Deferred Architectural Features**:
  - No vector databases or embeddings (uses deterministic metadata filtering).
  - No OCR for scanned or raster drawings (requires selectable PDF text).
  - No conversational agents or multi-turn dialogues.
  - No direct production database writes.
  - No web UI or REST API server (CLI-only phase).

---

## 8. Final CLI Milestone Verdict

The Engineering Data Copilot CLI Portfolio MVP satisfies all requirements for reproducibility, safety, auditability, and automated verification. The project is ready for portfolio review and presentation.
