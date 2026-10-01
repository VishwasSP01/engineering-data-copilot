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
- [x] **Step 10: Comparative Evaluation (Live Gemini vs. Deterministic Baseline)** — Completed.
  - **Artifacts Created & Updated**:
    - Evaluator Extension: `scripts/evaluate.py` (Added `--extractor {deterministic,gemini,both}` and `--model` CLI flags; integrated early retrieval abstention tracking, automatic retry disabling, API failure abort handling, side-by-side concordance analysis, and explicit rate denominators).
    - Comparison Reports: `evaluation/reports/comparison_report.json` and `evaluation/reports/comparison_report.md` (Side-by-side per-case results, latency comparisons, token consumption breakdown, and failure/abstention analysis).
    - Project Documentation: `README.md` and `docs/PROGRESS.md`.
  - **Evaluation & Comparative Results (10 Synthetic Cases)**:
    - Deterministic Overall Pass Rate: 10 / 10 (100.0%)
    - Live Gemini Overall Pass Rate: 10 / 10 (100.0%)
    - Provider Concordance Rate: 10 / 10 (100.0% exact match across all outcomes and proposals)
    - Correction-Case Pass Rate: 2 / 2 (100.0%) on both providers (cm→mm and mm→cm)
    - Agreement-Case Pass Rate (`no_change`): 2 / 2 (100.0%) on both providers
    - Abstention-Case Pass Rate: 6 / 6 (100.0%) on both providers (`insufficient_evidence`, `ambiguous_evidence`, `needs_review`)
    - Citation Validity: 5 / 5 (100.0%) verified verbatim against isolated source PDF text
    - Model Requests Attempted: 5 / 10 (exactly 5 cases had extractable evidence passages)
    - Model Requests Succeeded: 5 / 5 (100.0% model extraction success)
    - Cases With No Model Call: 5 / 10 (50.0% of cases safely abstained during retrieval/validation before model invocation)
    - Resource & Performance Profile:
      * All-Cases Median Latency: 0.63 ms (deterministic) vs. 381.38 ms (Gemini)
      * Model-Called Cases Median Latency (5 Cases): 0.84 ms (deterministic) vs. 791.92 ms (Gemini; mean: 836.00 ms, range 762.31–953.60 ms)
      * Non-Model Cases Median Latency (5 Cases): 0.57 ms (deterministic) vs. 0.32 ms (Gemini)
      * Token Usage: 1,241 total tokens (967 prompt, 274 candidates) across all 5 model requests
      * Estimated Cost: null (unestimated; pricing rates external to API metadata)
    - Comparative Finding: Live `gemini-3.5-flash-lite` **matched** the deterministic baseline across all 10 synthetic test cases without improving or degrading decision quality. Downstream Decimal arithmetic and early retrieval boundary checks operated identically for both providers.
    - Limitations: Conclusions are strictly limited to the synthetic benchmark suite and do not claim to demonstrate production accuracy across complex real-world technical documents.
- [x] **Step 11: Varied Supplier Datasheet Evaluation Suite & Limitation Discovery** — Completed.
  - **Artifacts Created & Updated**:
    - Challenge Generator: `scripts/generate_challenge_suite.py` (Constructs 6 new isolated challenge cases with custom ReportLab layouts, strictly using mm/cm units and preserving component/revision metadata).
    - Challenge Cases: `evaluation/cases/challenge-01` through `challenge-06` (Each containing `record.json`, isolated `documents/` PDF, and isolated `extracted/` JSON).
    - Expected Outcomes: `evaluation/expected/challenge-01-complete-sentence.json` through `challenge-06-conflicting-statements.json` (Authored independently from document specifications).
    - Evaluator Extension: `scripts/evaluate.py` (Added `--suite {baseline,challenge,all}` support, challenge report generation, and failure stage attribution).
    - Evaluation Reports: `evaluation/reports/challenge_report.json` and `evaluation/reports/challenge_report.md` (Detailed baseline evaluation across the 6 challenge cases).
    - Regression Suite: `scripts/verify_sample.py` (Integrated Step 11 challenge suite verification without breaking Steps 3–8).
    - Project Documentation: `README.md` and `docs/PROGRESS.md`.
  - **Challenge Case Design & Specifications (6 Cases)**:
    1. `challenge-01-complete-sentence`: Nominal thickness stated within a complete sentence ("Under standard ambient conditions, the nominal thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots.").
    2. `challenge-02-table-value-unit-columns`: Physical dimensions formatted in a multi-column table with separate `Parameter`, `Nominal Value`, and `Unit` columns (`Thickness` | `15.0` | `mm`).
    3. `challenge-03-split-lines-label-measurement`: Attribute label and measurement wrapped across a line break (`Component Thickness:<br/>2.4 mm`).
    4. `challenge-04-distracting-measurements`: Thickness stated alongside concatenated length and width dimensions (`Package dimensions (length, width, thickness): 60.0 mm x 40.0 mm x 6.0 mm.`).
    5. `challenge-05-incorrect-revision`: Datasheet contains Revision B, while engineering record specifies Revision A.
    6. `challenge-06-conflicting-statements`: Datasheet contains two conflicting thickness statements (`0.8 cm` and `1.2 cm`) for the same component and revision.
  - **Deterministic Baseline Results (6 Challenge Cases)**:
    - Overall Pass Rate: **2 / 6 (33.3%)**
    - Correction-Case Pass Rate: **0 / 3 (0.0%)**
    - Agreement-Case Pass Rate (`no_change`): **0 / 1 (0.0%)**
    - Abstention-Case Pass Rate: **2 / 2 (100.0%)** (`insufficient_evidence` on Rev B mismatch, `ambiguous_evidence` on conflicting statements)
    - Citation Validity: **1 / 4 (25.0%)**
    - Median Latency: **0.39 ms** (mean: 0.53 ms)
  - **Limitation & Failure Stage Analysis**:
    - **All 4 layout failures failed at the `retrieval` stage**:
      * `challenge-01-complete-sentence`: Regex falsely paired the date digits `01` with word `is` as a unit, triggering the unit guardrail (`needs_review`) instead of extracting `1.2 cm`.
      * `challenge-02-table-value-unit-columns`: Table cells extracted across separate lines (`Thickness\n15.0\nmm`); line-by-line scanning failed to correlate the label with subsequent values.
      * `challenge-03-split-lines-label-measurement`: Newline split disconnected label from value; neither line individually matched candidate extraction regex.
      * `challenge-04-distracting-measurements`: Regex captured the adjacent length token (`60.0 mm`) after `thickness):`, proposing an incorrect correction (`6.0 cm`) instead of `no_change`.
    - **Guardrail Robustness**: Revision isolation (Case 5) and ambiguity detection (Case 6) passed reliably (100.0%), confirming that retrieval safety checks remain sound.
  - **Execution Constraint**: Zero Gemini API calls made in Step 11; suite kept fixed for subsequent provider comparison.


