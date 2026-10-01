# Engineering Data Investigation Copilot — Progress Tracker

## Implementation Steps

- [x] **Step 1: Repository setup** — Completed. Repository initialized, cloned, and opened in development environment.
- [x] **Step 2: Project brief** — Completed. Scope, requirements, schemas, success criteria, and evaluation defined in [PROJECT_BRIEF.md](PROJECT_BRIEF.md).
- [x] **Step 3: Synthetic Data & Datasheet Generation** — Completed.
  - **Artifacts Created**:
    - Record JSON: `data/records/unit-mismatch-001.json` (Component `COMP-001`, Rev `A`, thickness `0.8 mm`).
    - Supplier PDF: `data/documents/supplier-COMP-001.pdf` (Single-page ReportLab PDF, component `COMP-001`, Rev `A`, document `DOC-SUP-COMP-001`, exact passage: `"Component thickness: 0.8 cm."`, synthetic demonstration notice).
    - Expected Evaluation JSON: `evaluation/expected/unit-mismatch-001.json` (Evaluation-only ground truth with expected correction `8.0 mm`, document filename, page 1, exact passage, and deterministic arithmetic calculation).
    - Generator Script: `scripts/generate_sample.py`.
    - Verification Suite: `scripts/verify_sample.py`.
  - **Verification Results**:
    - JSON validity: Both `unit-mismatch-001.json` and expected evaluation JSON parsed and validated.
    - Identifier & revision alignment: Component ID (`COMP-001`) and revision (`A`) match exactly across record, PDF text, and expected evaluation.
    - PDF properties: Verified exactly 1 page with 1589 characters of selectable text, synthetic disclaimer banner, and exact supporting passage.
    - Deterministic arithmetic: \( 0.8\text{ cm} \times 10.0 = 8.0\text{ mm} \) verified.
- [x] **Step 4: Document Text Extraction with Citation Preservation** — Completed.
  - **Artifacts Created**:
    - Extraction Script: `scripts/extract_documents.py` (Reads strictly from `data/documents/`, extracts text per page, preserves source filename and 1-indexed page numbers, enforces failure reporting on unreadable/empty pages, isolates from `evaluation/expected/`).
    - Extracted Document JSON: `data/extracted/supplier-COMP-001.json`.
  - **Verification Results**:
    - JSON Validity: `data/extracted/supplier-COMP-001.json` parsed and validated.
    - Citation Integrity: Verified `source_file` is `supplier-COMP-001.pdf` and `page_number` is 1.
    - Content Preservation: Verbatim text extraction confirmed matching raw PDF text without rewriting, summarization, or supplementation.
    - Identifier & Measurement Preservation: Component ID (`COMP-001`), measurement (`0.8 cm`), and the exact passage (`"Component thickness: 0.8 cm."`) successfully extracted intact.
- [x] **Step 5: Deterministic Evidence Retrieval Baseline** — Completed.
  - **Artifacts Created**:
    - Retrieval Script: `scripts/retrieve_evidence.py` (CLI and module accepting a record JSON path, reading `data/extracted/` only, matching component ID and revision explicitly in document text, finding measurement passages, detecting conflicts, returning exact verbatim evidence).
    - Verification Suite Update: `scripts/verify_sample.py` (Extended to verify sample retrieval, unknown component, incorrect revision, missing measurement, and conflicting evidence).
  - **Verification Results**:
    - Existing sample: Correctly retrieved `"Component thickness: 0.8 cm."` citing `supplier-COMP-001.pdf`, page 1.
    - Unknown component: Returned `status: "insufficient_evidence"`.
    - Incorrect revision: Returned `status: "insufficient_evidence"`.
    - Missing measurement: Returned `status: "insufficient_evidence"`.
    - Conflicting evidence: Returned `status: "ambiguous_evidence"`.
    - Exact passage grounding: Verified that returned passage exists verbatim on cited extracted page.
- [x] **Step 6: Unit Mismatch Analysis & Deterministic Correction** — Completed.
  - **Artifacts Created**:
    - Investigation Script: `scripts/investigate_record.py` (CLI and module connecting record input → evidence retrieval → measurement parsing → Decimal unit conversion → comparison → structured correction proposal).
    - Verification Suite Update: `scripts/verify_sample.py` (Extended to verify sample proposal, agreement no_change, bidirectional conversion [cm to mm and mm to cm], abstentions, needs_review for unsupported units/malformed values, and citation preservation).
  - **Verification Results**:
    - Sample Mismatch: Record `0.8 mm` vs evidence `0.8 cm` yielded `correction_proposed` with proposed value `8.0 mm` and explicit conversion calculation `0.8 cm * 10 mm/cm = 8.0 mm`.
    - Value Agreement: Record `8.0 mm` vs evidence `0.8 cm` yielded `no_change` with `proposed_correction: null`.
    - Bidirectional Conversion: Verified reverse conversion (evidence `20.0 mm` with record `20.0 cm` → proposed `2.0 cm`; record `2.0 cm` → `no_change`).
    - Abstention Handling: Missing evidence returned `insufficient_evidence`; conflicting evidence returned `ambiguous_evidence`. Both contain no proposed correction.
    - Review Handling: Unsupported units (`in`) and non-numeric record values returned `needs_review` with no proposed correction.
    - Provenance & Integrity: Every valid decision preserved the exact citation; source records and supplier documents remained unmodified.
- [x] **Step 7: Evaluation Suite & Benchmark Runner** — Completed.
  - **Artifacts Created**:
    - Case Generator: `scripts/generate_evaluation_suite.py` (Generates 10 isolated synthetic benchmark test cases with separate document and extraction directories, plus explicit expected answer JSON files under `evaluation/expected/`).
    - Evaluation Runner: `scripts/evaluate.py` (Runs investigation across all 10 isolated cases, compares outcomes, proposals, citations, and verifies quoted passages directly against source PDF text; outputs JSON and Markdown reports).
    - Case Fixtures: `evaluation/cases/case-01` through `case-10` (Each with isolated `record.json`, `documents/`, and `extracted/`).
    - Ground Truth: `evaluation/expected/case-01` through `case-10` JSON files.
    - Evaluation Reports: `evaluation/reports/evaluation_report.json` and `evaluation/reports/evaluation_report.md`.
  - **Evaluation & Verification Results**:
    - Total Cases: 10 / 10 passed (100.0% pass rate).
    - Supported Corrections: 2 / 2 passed (both `cm` → `mm` and `mm` → `cm` proposed exact values).
    - Agreements: 2 / 2 passed (`no_change` with no proposed correction).
    - Negative Cases: 6 / 6 passed (unknown component, incorrect revision, missing measurement, conflicting evidence, unsupported unit, and malformed measurement).
    - Citation Validity: 5 / 5 (100.0%) verified verbatim against isolated source PDF text.
    - Investigation Latency: Median 0.39 ms, Mean 0.52 ms (measured separately from fixture generation).
    - Model Usage: 0 calls (deterministic rule-based baseline), Model Cost: N/A.
- [x] **Step 8: Model-Assisted Extraction & LLM Evaluation** — Completed.
  - **Artifacts Created & Updated**:
    - Extractor Framework: `scripts/extractors.py` (Structured Pydantic schema `MeasurementExtractionResponse`, `BaseMeasurementExtractor` interface, `DeterministicMeasurementExtractor` baseline, `GeminiMeasurementExtractor` adapter via official `google-genai` SDK, and prompt builder).
    - Investigation Workflow: `scripts/investigate_record.py` (Added `--extractor` CLI flag, integrated 5-point post-extraction verification guardrail, and attached `extractor` execution metadata with provider, model, latency, and token usage to all return paths).
    - Step 8 Verification Suite: `scripts/verify_step8_extractor.py` (Automated suite validating Pydantic schemas, prompt boundaries, deterministic baseline, and 7 mock Gemini scenarios with zero live network calls).
    - Unified Verification Suite: `scripts/verify_sample.py` (Integrated Step 8 test execution into end-to-end verification).
    - Dependency Manifest: `requirements.txt` (Added `pydantic>=2.0.0` and `google-genai>=1.0.0`).
    - Project Documentation: `README.md` (Documented `--extractor` switch, prerequisites, post-extraction guardrails, and live usage notice).
  - **Verification Results**:
    - Pydantic Schema Validation: Valid payloads parsed correctly; missing fields or invalid decimals in `found` status raised validation errors; `insufficient` and `ambiguous` statuses parsed without measurement fields.
    - Prompt Boundary Enforcement: Verified prompt supplies only requested measurement and cited passage without leaking target values or expected answers.
    - Deterministic Baseline: Maintained as default; verified structured extraction and execution metadata.
    - Mock Gemini Adapter Scenarios (Zero external network calls):
      * Valid extraction: Verified conversion of `0.8 cm` -> `8.0 mm` with execution metadata (`google-genai`, `gemini-2.5-flash`, `total_tokens: 70`).
      * Invented quote: Caught by grounding guardrail (`quote not in passage`) -> returned `needs_review` with no proposed correction.
      * Unsupported unit: Caught by unit guardrail (`in`) -> returned `needs_review` with no proposed correction.
      * Malformed output: Non-JSON and schema violations caught -> returned `needs_review` with no proposed correction.
      * Model abstentions: `insufficient` -> `insufficient_evidence`, `ambiguous` -> `ambiguous_evidence`.
      * Timeout and API failure: Caught cleanly without crashing -> returned `needs_review`.
      * Missing credentials: Handled gracefully -> returned `needs_review` with clear configuration guidance.
    - Regression Safety: All Step 3–7 checks continue to pass with 100% success rate.
    - Live Environment Status: Automated tests operated offline via injected mock clients; live Gemini API behavior is documented as not yet verified with production credentials.
- [x] **Step 9: Live Gemini Sample Investigation & Verification** — Completed.
  - **Artifacts Created & Updated**:
    - Environment Loading: `scripts/extractors.py` and `scripts/investigate_record.py` (Added minimal repository-root `.env` loading preserving shell environment variables; disabled automatic retries via `types.HttpRetryOptions(attempts=1)`).
    - Evaluation Reports: `evaluation/reports/live_investigation_report.json` and `evaluation/reports/live_investigation_report.md` (Documenting comparison against deterministic baseline, execution metrics, token counts, and full attempt history).
    - Project Documentation: `README.md` and `docs/PROGRESS.md`.
  - **Live Verification Results**:
    - Target: Synthetic sample `unit-mismatch-001` (Component `COMP-001`, Rev `A`, thickness `0.8 mm`).
    - Active Model: `gemini-3.5-flash-lite` via official `google-genai` SDK.
    - Model Extraction: Extracted nominal measurement `0.8 cm` for requested attribute `thickness`.
    - Citation Grounding: Exact quote `"Component thickness: 0.8 cm."` verified verbatim in `supplier-COMP-001.pdf` page 1.
    - Deterministic Arithmetic: Python Decimal logic converted `0.8 cm` to `8.0 mm` (`0.8 cm * 10 mm/cm = 8.0 mm`).
    - Investigation Outcome: `correction_proposed` with proposed value `8.0 mm`.
    - Data Integrity: Original engineering database record remained unmodified (`source_record_modified: false`).
    - Baseline Alignment: 100% agreement with deterministic baseline provider across extracted value, cited passage, and proposed correction.
    - Execution Metrics: Single generation request, 965.75 ms call latency, 247 total tokens (193 prompt, 54 candidate), cost left null.
    - Scope Clarification: Documented as a single successful live sample investigation, not an accuracy or generalization benchmark.

