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
- [x] **Step 12: Evidence Retrieval Improvements for Varied Datasheets** — Completed.
  - **Artifacts Created & Updated**:
    - Retrieval Implementation: `scripts/retrieve_evidence.py` (Decoupled evidence discovery from measurement parsing; preserved precise-passage retrieval when unambiguous direct specification lines exist; implemented contiguous verbatim section/page fallback with `context_type` provenance [`passage`, `section`, `page`]; maintained strict component ID, revision eligibility, and conflict detection guardrails; kept generic to any requested attribute).
    - Pipeline Integration: `scripts/investigate_record.py` (Propagates `retrieval_status` and `context_type` through investigation response metadata).
    - Evaluation Framework: `scripts/evaluate.py` (Evaluates retrieval success separately from end-to-end correctness; supports section containment for citation verification; dynamically attributes failure stages to `measurement extraction`; updates challenge reporting).
    - Verification Suite: `scripts/verify_sample.py` (Added Step 12 checks verifying section retrieval across all 4 challenge cases, guardrail abstentions, and challenge evaluation metrics).
    - Evaluation Reports: `evaluation/reports/challenge_report.json` and `evaluation/reports/challenge_report.md` (Updated with Step 12 retrieval and evaluation metrics).
    - Project Documentation: `README.md` and `docs/PROGRESS.md`.
  - **Verification & Evaluation Results**:
    - **Retrieval Success Rate**: **6 / 6 (100.0%)** across all challenge cases (all 4 previously failing retrieval cases now successfully extract verbatim evidence sections containing the requested label, value, unit, and table headers).
    - **End-to-End Pass Rate**: **4 / 6 (66.7%)** (up from 2 / 6 in Step 11).
      * `challenge-01-complete-sentence`: **FAIL** (`needs_review`). Retrieval: SUCCESS (verbatim Section 2 retrieved). Failure stage: `measurement extraction` (deterministic regex falsely captured component ID digits `01` with word `is` as a unit, triggering unit guardrail).
      * `challenge-02-table-value-unit-columns`: **PASS** (`correction_proposed`, 1.5 cm). Retrieval: SUCCESS (parameter table section with headers retrieved). Deterministic extraction: SUCCESS (parsed `15.0 mm` across table lines).
      * `challenge-03-split-lines-label-measurement`: **PASS** (`correction_proposed`, 0.24 cm). Retrieval: SUCCESS (wrapped label/measurement section retrieved). Deterministic extraction: SUCCESS (parsed `2.4 mm` across line break).
      * `challenge-04-distracting-measurements`: **FAIL** (`correction_proposed` with 6.0 cm vs. expected `no_change`). Retrieval: SUCCESS (package dimensions section retrieved). Failure stage: `measurement extraction` (deterministic regex greedily captured adjacent length dimension `60.0 mm` instead of thickness `6.0 mm`).
      * `challenge-05-incorrect-revision`: **PASS** (`insufficient_evidence`). Retrieval: SUCCESS (revision isolation guardrail correctly abstained).
      * `challenge-06-conflicting-statements`: **PASS** (`ambiguous_evidence`). Retrieval: SUCCESS (ambiguity resolution guardrail correctly abstained).
    - **Failure Stage Transition**: Zero cases failed at `retrieval` (down from 4 in Step 11). Remaining failures cleanly shifted to `measurement extraction`.
    - **Regression Safety**: All Step 3–8 and Step 11–12 verification checks passed (100%). Zero Gemini API calls made.
- [x] **Step 13: Comparative Evaluation on Varied Datasheets (Gemini vs. Deterministic)** — Completed.
  - **Goal & Scope**: Measure whether Gemini adds value once relevant evidence reaches the extractor across the 6 challenging synthetic supplier datasheets (complete sentence, multi-column table, split lines, distracting dimensions, revision mismatch, and conflicting statements) following Step 12 retrieval improvements.
  - **Frozen Baseline State**:
    - Git Commit: `c75b443b1b906bf17ef506788e1b396cf4a321e2`
    - Gemini Model: `gemini-3.5-flash-lite`
    - Fixtures, expected answers, retrieval logic, and extraction prompts frozen without modification.
  - **Artifacts Created & Updated**:
    - Evaluator Extension: `scripts/evaluate.py` (Extended `run_comparison` to support `--suite challenge`; added `generate_challenge_comparison_markdown`; tracked retrieval success separately from decision correctness; tracked requests attempted, completed, and skipped; added explicit latency medians for model-called vs. non-model cases; refined dynamic failure stage categorization into `retrieval`, `extraction`, `validation`, and `api`).
    - Comparison Reports: `evaluation/reports/challenge_comparison_report.json` and `evaluation/reports/challenge_comparison_report.md` (Side-by-side per-case evaluation, concordance rate, failure stage breakdown, request and token metrics).
    - Baseline Challenge Reports: `evaluation/reports/challenge_report.json` and `evaluation/reports/challenge_report.md`.
    - Project Documentation: `README.md` and `docs/PROGRESS.md`.
  - **Comparative Benchmark Results (6 Challenge Cases)**:
    - **Overall Pass Rate (End-to-End)**:
      * Deterministic Baseline: **4 / 6 (66.7%)**
      * Live Gemini (`gemini-3.5-flash-lite`): **5 / 6 (83.3%)** (**Gemini Improved**)
    - **Retrieval Success Rate**: **6 / 6 (100.0%)** on both providers (identical; both operate on verbatim retrieved sections).
    - **Provider Concordance Rate**: **5 / 6 (83.3%)**
    - **Correction-Case Pass Rate**: 2 / 3 (66.7%) on both providers (`challenge-02` and `challenge-03` passed).
    - **Agreement-Case Pass Rate (`no_change`)**: 0 / 1 (0.0%) deterministic vs. **1 / 1 (100.0%)** Gemini.
    - **Abstention-Case Pass Rate**: 2 / 2 (100.0%) on both providers (`challenge-05` and `challenge-06` safely abstained).
    - **Citation Validity**: 4 / 4 (100.0%) on both providers.
    - **Model Request Control**:
      * Requests Attempted: 4 / 6
      * Requests Completed: 4 / 4 (100.0% completion, zero retries)
      * Cases Without Model Call (Skipped): 2 / 6 (33.3%; `challenge-05` and `challenge-06` safely abstained during retrieval).
    - **Performance & Latency Profile**:
      * All Cases Median Latency: 0.46 ms (deterministic) vs. 821.71 ms (Gemini)
      * Model-Called Cases Median Latency (4 Cases): 872.17 ms (Gemini; mean: 893.54 ms, range 808.82–1020.98 ms)
      * Non-Model Cases Median Latency (2 Cases): 0.46 ms (deterministic) vs. 0.43 ms (Gemini)
    - **Resource Consumption**:
      * Token Usage: 1,395 total tokens (1,142 prompt, 253 candidate) across 4 generation requests.
      * Estimated Cost: null (unestimated; pricing rates external to API metadata).
  - **Comparative Findings & Value-Add Analysis**:
    1. **Where Gemini Improved Over Baseline**:
       - `challenge-04-distracting-measurements`: The datasheet specified `"Package dimensions (length, width, thickness): 60.0 mm x 40.0 mm x 6.0 mm."` The deterministic regex extractor greedily captured the adjacent length token (`60.0 mm`) and proposed an incorrect correction (`6.0 cm`, FAIL). Gemini correctly resolved the multi-dimension tuple correspondence, identified thickness as `6.0 mm` (converting to `0.6 cm`), and confirmed data agreement (`no_change`, **PASS**).
    2. **Where Gemini Matched Baseline**:
       - `challenge-02-table-value-unit-columns`: Both passed (`correction_proposed`, 15.0 mm -> 1.5 cm).
       - `challenge-03-split-lines-label-measurement`: Both passed (`correction_proposed`, 2.4 mm -> 0.24 cm).
       - `challenge-05-incorrect-revision`: Both passed (`insufficient_evidence`, retrieval revision guardrail early abstention).
       - `challenge-06-conflicting-statements`: Both passed (`ambiguous_evidence`, retrieval conflict guardrail early abstention).
    3. **Where Gemini Regressed / Worsened**: Zero regressions (Gemini passed all cases that deterministic passed).
    4. **Validation Rejection of Potentially Correct Extraction (`challenge-01`)**:
       - On `challenge-01-complete-sentence`, Gemini extracted the correct numerical value (`1.2`) and unit (`cm`). However, in its supporting quote, Gemini normalized the PDF newline in `"is\nmanufactured"` to a single space `"is manufactured"`.
       - Because downstream Guardrail 1 requires exact verbatim substring containment (`quote in passage`), the literal string check rejected the extraction (`needs_review`).
       - As required by Step 13, runtime validation was kept strict and unmodified. The failure was documented and classified as a `"validation"` failure stage (rather than `retrieval` or `extraction`).
  - **Limitations Notice**: All findings are strictly bounded to the 6 synthetic challenge cases and do not claim to demonstrate generalization across unconstrained production engineering documents.
- [x] **Step 14: Improved Quote Alignment and Measurement Binding** — Completed.
  - **Goal & Scope**: Address failures identified in Step 13 (`challenge-01` validation rejection from PDF line-breaks, and `challenge-04` deterministic greedy attribute binding) by implementing whitespace-aware quote alignment and labelled measurement binding without making live Gemini API calls.
  - **Core Implementations**:
    1. **Whitespace-Aware Quote Alignment (`align_quote_to_passage`)**:
       - Preserves strict literal substring matching as the primary check.
       - Implements a token index mapping fallback that permits only whitespace differences between model quotes and source text (e.g., spaces vs newlines).
       - Requires a unique contiguous source span; returns that original verbatim span as citation, retaining the model quote separately for audit.
       - Strictly rejects modified numbers, modified units, invented words, missing matches, and ambiguous (multiple) matches without fuzzy matching.
       - Integrated into downstream validation Guardrail 1 and Guardrail 4 in `scripts/investigate_record.py`.
    2. **Deterministic Labelled Tuple Binding (`parse_labelled_tuple`)**:
       - Parses multi-attribute tuples such as `(length, width, thickness): 60 mm x 40 mm x 6 mm` and maps target attributes to their specific positional indices.
       - Avoids greedy selection of the first number following attribute keywords.
       - Safely abstains (`needs_review`) when label count does not match value count, multiple labels match target, or units are missing.
       - Integrated as Pattern 0 in `DeterministicMeasurementExtractor` in `scripts/extractors.py`.
    3. **Evaluator Terminology & Metrics Clarification**:
       - Separated evidence retrieval success (cases expecting evidence) from retrieval abstention (cases expecting missing/ambiguous evidence).
       - Formatted pass-rate comparisons in percentage points (`pp`).
    4. **Comprehensive Offline Verification Suite (`scripts/verify_sample.py`)**:
       - Strict literal matching and whitespace alignment tests.
       - Rejection tests for modified numbers, modified units, invented words, and ambiguous matches.
       - Positional mapping and shared trailing unit propagation for labelled tuples.
       - Abstention checks for label/value count mismatches, duplicate labels, and missing units.
       - Replay validation of frozen Step 13 `challenge-01` model extraction (1.2 cm -> 12.0 mm correction proposal).
       - Record and source document immutability verification via SHA-256 digests.
       - Evaluation verification on challenge suite: 5/6 pass deterministically, with `challenge-01` honestly documented as remaining regex limitation.
  - **Benchmark Results (Challenge Suite - Deterministic)**:
    - Overall Pass Rate: **5 / 6 (83.3%)** (an increase of 16.7 percentage points from 4/6 [66.7%] in Step 12, and 50.0 percentage points from 2/6 [33.3%] in Step 11).
    - Evidence Retrieval Success Rate: **4 / 4 (100.0%)** on cases with evidence.
    - Retrieval Abstention Success Rate: **2 / 2 (100.0%)** on missing/conflicting cases.
    - Combined Retrieval Accuracy: **6 / 6 (100.0%)**.
    - Citation Validity: **4 / 4 (100.0%)**.
    - Resolved Case: `challenge-04-distracting-measurements` successfully resolved deterministically (`no_change`).
    - Remaining Limitation: `challenge-01-complete-sentence` fails deterministically at `measurement extraction` due to interstitial sentence structure.
  - **Constraints Enforced**:
    - Zero live Gemini API calls made.
    - Fixtures in `evaluation/cases/` and expected answers in `evaluation/expected/` untouched.
    - Frozen Step 13 reports (`challenge_comparison_report.json` and `.md`) preserved without modification.
    - `.env` strictly excluded from git tracking.
- [x] **Step 15: Evaluate Updated Evidence Validation with Live Gemini on Challenge Cases** — Completed.
  - **Goal & Scope**: Evaluate the updated evidence validation pipeline (with whitespace-aware quote alignment and labelled tuple measurement binding from Step 14) using live `gemini-3.5-flash-lite` against the 6 challenging synthetic supplier datasheets.
  - **Frozen Baseline Versions**:
    * Git Commit: `cfcbbda5b5df1a915a2e074caf015a3fbd34f4be`
    * Configured Model: `gemini-3.5-flash-lite` (max attempts = 1, automatic retries disabled)
    * Challenge Fixtures: `evaluation/cases/` (6 isolated synthetic challenge cases)
    * Expected Answers: `evaluation/expected/` (frozen expected JSONs)
    * Retrieval Implementation: `scripts/retrieve_evidence.py` (decoupled retrieval with verbatim section/page fallback)
    * Extraction Prompt: `scripts/extractors.py:build_extraction_prompt` (strict boundary extraction)
    * Validation Implementation: `scripts/investigate_record.py` (whitespace-aware quote alignment & tuple parsing)
  - **Comparative Benchmark Results (Challenge Suite: 6 Cases)**:
    * **Overall Pass Rate**: Deterministic **5 / 6 (83.3%)** vs. Live Gemini **6 / 6 (100.0%)** (+16.7 percentage points improvement).
    * **Evidence Retrieval Success Rate**: **4 / 4 (100.0%)** for both providers on cases expecting evidence (`challenge-01` through `challenge-04`).
    * **Retrieval Abstention Success Rate**: **2 / 2 (100.0%)** for both providers on missing/conflicting cases (`challenge-05` and `challenge-06`).
    * **Combined Retrieval Accuracy**: **6 / 6 (100.0%)** for both providers.
    * **Correction-Case Pass Rate**: Deterministic **2 / 3 (66.7%)** vs. Live Gemini **3 / 3 (100.0%)**.
    * **Agreement-Case Pass Rate (`no_change`)**: Deterministic **1 / 1 (100.0%)** vs. Live Gemini **1 / 1 (100.0%)**.
    * **Abstention-Case Pass Rate**: Deterministic **2 / 2 (100.0%)** vs. Live Gemini **2 / 2 (100.0%)**.
    * **Citation Validity**: **4 / 4 (100.0%)** (4 valid citations out of 4 cases producing citations).
    * **Provider Concordance**: **5 / 6 (83.3%)** matching outcomes.
    * **API Execution Metrics**:
      - Requests Attempted: 4 / 6 (max 6 budget preserved).
      - Requests Completed: 4 / 4 (100.0% completion, zero retries).
      - Requests Skipped (Early Retrieval Abstention): 2 / 6 (33.3%; `challenge-05` and `challenge-06` abstained before model invocation).
    * **Performance & Latency Profile**:
      - All Cases Median Latency: 0.48 ms (deterministic) vs. 813.33 ms (Gemini).
      - Model-Called Cases Median Latency (4 Cases): 880.62 ms (Gemini; mean: 872.25 ms).
      - Non-Model Cases Median Latency (2 Cases): 0.48 ms (deterministic) vs. 0.23 ms (Gemini).
    * **Resource Consumption**:
      - Token Usage: 1,395 total tokens (1,142 prompt tokens, 253 candidate tokens) across 4 live generation requests.
      - Estimated Cost: null (unestimated; pricing rates external to API metadata).
  - **Comparative Evolution Across Milestone Steps**:
    | Step | Mode | Deterministic Pass Rate | Gemini Pass Rate | `challenge-01` (Sentence) | `challenge-04` (Tuple) | Key Finding |
    |---|---|---|---|---|---|---|
    | **Step 13** | Live API Call | 4 / 6 (66.7%) | 5 / 6 (83.3%) | Gemini FAIL (strict quote newline) | Gemini PASS (`no_change`) | Gemini resolved multi-dimension tuple; newline in sentence triggered strict verbatim rejection |
    | **Step 14** | Offline Replay | 5 / 6 (83.3%) | 6 / 6 (100.0%) [Replay] | Replay PASS (whitespace mapped) | Det PASS (tuple parsed) | Token index mapping aligned quote offline; labelled tuple parsed deterministically |
    | **Step 15** | Live API Call | 5 / 6 (83.3%) | **6 / 6 (100.0%)** | **Gemini PASS (live)** | **Gemini PASS (live)** | Live validation confirmed end-to-end; whitespace alignment resolved `challenge-01` live |
  - **Key Step 15 Findings & Value-Add Analysis**:
    1. **Live Resolution of `challenge-01-complete-sentence`**:
       - In Step 13, Gemini extracted `"1.2 cm"` but formatted the supporting quote with a single space (`"is manufactured"`) instead of the source PDF's newline (`"is\nmanufactured"`), triggering Guardrail 1 literal rejection (`needs_review`).
       - In Step 15, whitespace-aware quote alignment (`align_quote_to_passage`) cleanly mapped the model quote back to the exact contiguous source span containing the newline, while strictly maintaining character fidelity and rejection of altered numbers/units. Downstream Decimal conversion computed `1.2 cm * 10 = 12.0 mm`, proposing correction to `12.0 mm` (**PASS**).
       - Deterministic baseline still fails on `challenge-01` at `measurement extraction` due to interstitial prose (`"of component COMP-C01 is"`), proving Gemini's semantic flexibility adds measurable value on unstructured natural language sentences (+16.7 percentage points).
    2. **Safety & Early Abstention Preserved**:
       - On `challenge-05-incorrect-revision` and `challenge-06-conflicting-statements`, retrieval guardrails aborted locally with `insufficient_evidence` and `ambiguous_evidence`, completely bypassing the model extractor and saving 33.3% of API requests.
    3. **Zero Regressions & Full Deterministic Math**:
       - Live Gemini achieved 100% concordance on all cases passed by the deterministic baseline.
       - All unit conversions (`1.2 cm -> 12.0 mm`, `15.0 mm -> 1.5 cm`, `2.4 mm -> 0.24 cm`, `6.0 mm -> 0.6 cm`) were computed via deterministic Python `Decimal` arithmetic.
  - **Generated Artifacts**:
    * `evaluation/reports/step15_challenge_comparison_report.json`
    * `evaluation/reports/step15_challenge_comparison_report.md`
    * Historical Step 13 reports (`challenge_comparison_report.json` and `.md`) preserved without alteration.
  - **Limitations Notice**: Findings are strictly bounded to the 6 synthetic challenge cases and do not claim generalization across unconstrained production engineering documents.
- [x] **Step 16: Reproducible Setup and Automated Offline CI Checks** — Completed.
  - **Goal & Scope**: Ensure a fresh checkout runs reliably and automated GitHub Actions CI detects regressions without credentials or live API calls, preserving the honest 5/6 challenge baseline.
  - **Environment & Dependency Lock**:
    * Documented Supported Python: Python 3.9+ (tested on Python 3.9.6).
    * Created `requirements-lock.txt` pinning all direct and transitive dependencies (`annotated-types`, `anyio`, `certifi`, `cffi`, `charset-normalizer`, `cryptography`, `exceptiongroup`, `google-auth`, `google-genai`, `h11`, `httpcore`, `httpx`, `idna`, `pillow`, `pyasn1`, `pyasn1_modules`, `pycparser`, `pydantic`, `pydantic_core`, `pypdf`, `reportlab`, `requests`, `tenacity`, `typing-inspection`, `typing_extensions`, `urllib3`, `websockets`).
    * Installation command: `pip install -r requirements-lock.txt`.
  - **Fresh Checkout & Isolated Verification**:
    * Verified end-to-end setup in a clean temporary checkout with an isolated virtualenv, without copying `.env` or existing `.venv`.
    * Validated `generate_sample.py` and `extract_documents.py` for fresh setup.
    * Verified `verify_step8_extractor.py` (7 mock scenarios, Pydantic validation, prompt boundaries) passed 100% offline.
    * Verified `verify_sample.py` (Steps 3–14 verification suite) passed 100% offline.
    * Verified `evaluate.py --extractor deterministic --suite baseline` achieved 10/10 (100.0%).
    * Verified `evaluate.py --extractor deterministic --suite challenge` achieved 5/6 (83.3%), with `challenge-01` honestly preserved as the known regex limitation on interstitial prose.
  - **Regression-Proof Evaluator Exit Codes**:
    * Updated `scripts/evaluate.py` to differentiate the expected 5/6 challenge baseline from regressions. An unexpected failure (or regression on any other case) exits with code 1.
  - **Automated GitHub Actions CI Workflow (`.github/workflows/ci.yml`)**:
    * Triggers on `push` and `pull_request` targeting `main`.
    * Sets up Python 3.9 on `ubuntu-latest`, installs locked dependencies, generates sample data and extracted text, runs offline mock and verification suites, executes baseline and challenge evaluations, and uploads evaluation reports as artifacts.
    * Runs strictly offline with zero live network calls and zero API key requirements.
  - **Documentation & Instructions**:
    * Updated `README.md` with supported environment, fresh-checkout setup, data generation, clear offline vs. live commands, and CI workflow details.
- [x] **Step 17: CLI Demo and Final Project Documentation** — Completed.
  - **Goal & Scope**: Prepare interview-ready CLI walkthrough and refined project documentation, update GitHub Actions CI to Python 3.13, accurately document tested environments, and embed architecture diagrams.
  - **CI Upgrade to Python 3.13**:
    * Updated `.github/workflows/ci.yml` from Python 3.9 to Python 3.13 on `ubuntu-latest`.
    * Preserved all dependency pins in `requirements-lock.txt`.
    * Verified automated CI run passes completely offline with zero credentials or network transit.
  - **Accurate Environment Documentation**:
    * Documented tested environments accurately: macOS (Darwin arm64) with Python 3.9.6, and Linux (`ubuntu-latest` / Ubuntu 24.04 x86_64) with Python 3.13 via GitHub Actions.
    * Explicitly avoided unsubstantiated claims regarding Windows or untested Python versions.
  - **Refined Project Documentation (`README.md`)**:
    * Structured for first-time reviewers: clear problem definition and narrowly scoped solution.
    * Implemented technology stack: `pypdf`, `reportlab`, `pydantic`, Python standard library `decimal.Decimal`, `google-genai`.
    * Embedded Mermaid architecture diagram showing end-to-end pipeline (`record -> eligible retrieval -> extraction [deterministic / Gemini] -> source-quote validation -> Decimal conversion -> proposal/abstention`), keeping expected answers connected solely to the evaluator.
    * Included one copy-paste deterministic investigation command with its actual JSON output.
    * Documented optional live Gemini setup and execution commands with safety guardrail notes.
    * Honest evaluation presentation: baseline 10/10, challenge 5/6 deterministic vs. 6/6 live Gemini, with explicit limitation notice that results reflect synthetic benchmark fixtures rather than claims of generalized production accuracy.
    * Explicitly listed deferred features (no vector DB, no OCR, no web UI/API server).
  - **Interactive CLI Demo Guide (`docs/DEMO.md`)**:
    * Created interview-ready walkthrough covering 4 core scenarios: supported discrepancy correction (`unit-mismatch-001`), safety abstentions on conflicting evidence (`case-08`) and revision mismatches (`challenge-05`), demonstrated Gemini value-add on unstructured sentence prose (`challenge-01`), and automated offline CI verification.
    * All demo CLI commands tested and verified 100% offline; saved live model outputs clearly labeled as historical artifacts.
- [x] **Step 18: Final Review of the CLI Portfolio MVP** — Completed.
  - **Goal & Scope**: Complete independent verification of the CLI Portfolio MVP in an isolated fresh checkout, audit documentation against actual behavior, verify architecture diagrams, confirm security decoupling, and produce the final milestone review report.
  - **Fresh Checkout & Quickstart Verification**:
    * Verified quickstart commands in a clean scratch checkout without `.env`, `.venv`, or `data/extracted/`.
    * Locked dependencies installed cleanly via `pip install -r requirements-lock.txt`.
    * Verified `generate_sample.py` and `extract_documents.py`.
    * Passed all offline verification suites (`verify_sample.py`, `verify_step8_extractor.py`).
    * Confirmed baseline evaluation pass rate at 10/10 (100.0%) and challenge evaluation pass rate at 5/6 (83.3%) with `challenge-01` sentence regex limitation preserved.
    * Executed all offline demo commands from `docs/DEMO.md` with zero Gemini API calls.
  - **Security & Decoupling Audit**:
    * Confirmed runtime investigation code never reads `evaluation/expected/`.
    * Confirmed credentials (`.env`) and virtual environments (`.venv/`) remain untracked and excluded.
    * Confirmed no Gemini API calls occurred during offline verification or demo execution.
    * Bounded network statements accurately: package installation and CI setup require network transit; offline verification tests run locally with zero API calls.
  - **Architecture Diagram Verification**:
    * Updated Mermaid architecture diagram in `README.md` and `docs/DEMO.md` to explicitly show the document corpus as input to retrieval, accurately label record inputs and evidence passages, illustrate early safety abstention branching directly from retrieval, and connect expected answers solely to the evaluator.
  - **Generated Review Artifact**:
    * Produced comprehensive review document [`docs/CLI_MVP_REVIEW.md`](docs/CLI_MVP_REVIEW.md).
- [x] **Step 19: Add Minimal FastAPI Investigation Service** — Completed.
  - **Goal & Scope**: Expose the verified engineering investigation workflow through an HTTP service while preserving existing CLI behavior and offline evaluation guarantees.
  - **Dependencies & Environment**:
    * Added `fastapi>=0.115.0` and `uvicorn>=0.30.0` to `requirements.txt`.
    * Generated reproducible pins in `requirements-lock.txt` (`fastapi==0.128.8`, `uvicorn==0.39.0`, `starlette==0.49.3`, `click==8.1.8`, `annotated-doc==0.0.5`).
    * Verified compatibility with Python 3.13 in CI and Python 3.9.6 locally.
  - **FastAPI Endpoints (`api/main.py` & `api/schemas.py`)**:
    * `GET /health`: Returns service health status (`{"status": "healthy", "service": "engineering-data-copilot", "version": "1.0.0"}`) without requiring credentials or external services.
    * `POST /investigations`: Accepts an engineering record matching the existing schema; accepts extractor selection (`deterministic` [default] or `gemini`) via query param or request body; returns structured result through explicit Pydantic response schema (`InvestigationResponse`).
  - **Direct Workflow Reuse & Async Execution**:
    * Refactored `retrieve_evidence` and `investigate_record` to accept in-memory dictionary records alongside file paths.
    * Avoided CLI subprocesses and temporary request files.
    * Executed investigation off the async event loop via `asyncio.to_thread` to maintain high concurrency.
  - **Server-Configured Document Corpus & Sanitization**:
    * API clients cannot supply filesystem paths, credentials, or expected answers.
    * Document references strip internal filepaths; retrieval operates strictly against the server-configured `data/extracted/` directory.
    * Error messages and responses sanitize internal paths, prompts, and environment values.
  - **Structured HTTP Status Mapping**:
    * HTTP 200: All business outcomes, including corrections proposed, agreements (`no_change`), and safe data abstentions (`insufficient_evidence`, `ambiguous_evidence`, `needs_review`).
    * HTTP 422: Malformed request payloads (missing required fields, non-numeric values, or invalid extractors).
    * HTTP 503: Provider configuration failure (`PROVIDER_NOT_CONFIGURED`, e.g. missing API key or dependencies).
    * HTTP 502: Upstream AI provider request failure (`PROVIDER_REQUEST_FAILED`).
    * Distinguished service failures using structured metadata (`ExtractorResult.error_type`) rather than fragile substring matching.
  - **Offline API Integration Tests (`tests/test_api.py`)**:
    * Health check returns 200 without external dependencies.
    * End-to-end investigation with deterministic extractor reproduces the 0.8 mm -> 8.0 mm correction.
    * API output matches CLI output for identical input (concordance verified).
    * Malformed requests rejected with HTTP 422 (`error_code: VALIDATION_ERROR` or `INVALID_EXTRACTOR`).
    * Business abstentions return HTTP 200 with appropriate outcome and no correction.
    * Provider configuration failure returns HTTP 503 (`PROVIDER_NOT_CONFIGURED`).
    * Upstream provider request failure returns HTTP 502 (`PROVIDER_REQUEST_FAILED`).
    * Verified immutability of input records and stored documents via SHA-256 digests.
    * Zero live Gemini API calls during tests.
  - **Automated CI Integration**:
    * Added `Run FastAPI offline integration tests` step to `.github/workflows/ci.yml`.
- [x] **Step 20: Citation-Preserving Document Chunks and Pretrained Embeddings** — Completed.
  - **Goal & Scope**: Generate pretrained semantic embeddings and citation-preserving chunks from supplier document text without connecting a vector database or replacing default retrieval.
  - **Embedding Model & Environment**:
    * Model: `sentence-transformers/all-MiniLM-L6-v2` pinned to resolved HuggingFace commit SHA `1110a243fdf4706b3f48f1d95db1a4f5529b4d41`.
    * Dimension: 384 finite float32 values.
    * Runtime: CPU inference exclusively (`device="cpu"`, `batch_size=32`).
    * Normalization: Unit Euclidean norm (`normalize_embeddings=True`, verified $\|v\|_2 \approx 1.0 \pm 10^{-5}$).
    * Frozen Weights: Pretrained model weights are never trained or fine-tuned.
  - **Optional Dependencies Strategy**:
    * Created `requirements-embeddings.txt` pinning exact versions (`sentence-transformers==5.1.2`, `torch==2.8.0`, `transformers==4.57.6`, `tokenizers==0.22.2`, `numpy==2.0.2`, `safetensors==0.7.0`, `huggingface-hub==0.36.2`, `scikit-learn==1.6.1`, `scipy==1.13.1`).
    * Preserved lightweight core dependencies in `requirements.txt` and `requirements-lock.txt` so that core CLI and API checks do not require heavy PyTorch or model downloads.
  - **Citation-Preserving Chunking (`scripts/embed_documents.py`)**:
    * Single-Page Invariance: Chunks never cross page boundaries.
    * Exact Verbatim Spans: Character offsets (`start_char`, `end_char`) strictly reproduce original page text (`page_text[start:end] == chunk_text`).
    * Tokenizer-Aware Boundaries: Imposed a maximum limit of 250 tokens per chunk (including `[CLS]` and `[SEP]` special tokens within the 256-token limit), completely eliminating silent truncation.
    * Context & Structure Preservation: Preserved measurement lines and parameter tables as coherent units without splitting rows or attributes.
    * Authoritative Document Identity: Derived component ID, revision, and document ID strictly from document text regex headers. Rejects documents with missing or conflicting identities rather than guessing. Never consults expected answers or records.
  - **Isolated Storage & Manifest (`data/embeddings/`)**:
    * Saved `chunks.json` (metadata, offsets, SHA-256 digests, and authoritative identifiers).
    * Saved `embeddings.npy` (binary NumPy float32 matrix of shape `(num_chunks, 384)`).
    * Saved `manifest.json` (execution metadata, model commit SHA, dimensions, chunking settings, and file integrity hashes).
    * Added `data/embeddings/` to `.gitignore` to prevent committing generated vectors or caches.
  - **Comprehensive Verification (`scripts/verify_step20_embeddings.py`)**:
    * Vector Integrity: Verified 100% of vectors have 384 finite float values and unit Euclidean norms (min=1.000000, max=1.000000).
    * Verbatim Reproduction: Verified character offsets reproduce page text with 100% exact character fidelity.
    * Deterministic Reproducibility: Confirmed repeated CPU inference yields identical vectors with $0.00$ numerical difference ($< 10^{-5}$).
    * Offline Cached Execution: Verified model loads from local HuggingFace cache using `local_files_only=True` without making external network calls.
    * Safety Identity Rejection: Verified rejection of missing component IDs, ambiguous component IDs, missing revisions, and ambiguous revisions.
    * Cosine Similarity Demonstration: Successfully matched "Physical Dimensions Query" to Chunk 3 (Physical Dimensions, similarity 0.5112) and "Product Overview Query" to Chunk 2 (Product Overview, similarity 0.6599). Documented disclaimer that semantic dot-product properties do not replace or benchmark document retrieval accuracy.
  - **Lightweight Offline Tests & CI (`tests/test_chunking.py`)**:
    * Added 7 unit tests verifying verbatim reproduction, offset accuracy, SHA-256 calculation, and identity safety rules offline without requiring model downloads or PyTorch.
    * All 15 unit tests in `tests/` pass in 0.026s.
- [x] **Step 21: Persist Document Embeddings in PostgreSQL/pgvector** — Completed.
  - **Goal & Scope**: Deploy a local containerized PostgreSQL service with the `pgvector` extension to persist citation-preserving document chunks, metadata, and 384-dimensional pretrained embeddings. Verify storage integrity, schema idempotency, volume persistence, metadata filtering, and cosine nearest-neighbor query execution without connecting vector retrieval to the production investigation pipeline or adding LangChain/LangGraph.
  - **Docker Compose Service (`docker-compose.yml`)**:
    * Pinned Image: `pgvector/pgvector:0.8.0-pg16` running PostgreSQL 16.10 with pgvector 0.8.0 on host architecture (`linux/arm64`).
    * Persistent Storage: Named volume `copilot_pgvector_data` mounted at `/var/lib/postgresql/data`.
    * Host Port Binding: Bound to `127.0.0.1:${POSTGRES_PORT:-5432}`.
    * Environment Configuration: Configured via `.env` (`POSTGRES_DB=copilot_db`, `POSTGRES_USER=copilot_user`, `POSTGRES_PASSWORD=copilot_password`), with defaults provided in `.env.example`. Passwords are never committed or logged.
    * Health Check: Configured via `pg_isready -U ${POSTGRES_USER:-copilot_user} -d ${POSTGRES_DB:-copilot_db}` with 3s intervals and 5 retries.
  - **Database Schema Migration (`scripts/init_db.sql`)**:
    * Active Extension: `CREATE EXTENSION IF NOT EXISTS vector;` (pgvector 0.8.0).
    * Table `document_chunks`: Stores 17 fields preserving complete document provenance, verbatim text, character offsets, content hash, component ID, revision, document ID, model name, model revision, and the 384-dimensional embedding vector (`embedding vector(384)`).
    * Unique Constraint: `CONSTRAINT uq_document_chunks_corpus_chunk UNIQUE (corpus_id, chunk_id)` guaranteeing idempotent chunk upserts.
    * Composite Metadata Index: `idx_document_chunks_identity` on `(corpus_id, component_id, revision)`.
    * Cosine Vector Index: `idx_document_chunks_embedding_cosine` on `embedding` using `hnsw (embedding vector_cosine_ops)`.
  - **Optional Dependencies (`requirements-database.txt`)**:
    * Pinned PostgreSQL v3 driver `psycopg[binary]==3.2.13` and `pgvector==0.4.2` to keep base CLI and CI dependencies lightweight.
  - **Batch Ingestion CLI (`scripts/ingest_embeddings.py`)**:
    * Validation: Validates presence of `manifest.json`, `chunks.json`, and `embeddings.npy`; enforces model dimension == 384, verifies vector finiteness and unit normalization ($\|v\|_2 \approx 1.0$), and verifies exact chunk-vector row count alignment.
    * Parameterized Transactional Upsert: Uses `INSERT ... ON CONFLICT (corpus_id, chunk_id) DO UPDATE SET ...` to guarantee idempotent writes.
    * Execution: Ingested all 4 document chunks into `copilot_db.document_chunks` in 0.027s. Repeated runs confirmed exact 4-row stability with 0 duplicate rows.
  - **Comprehensive Verification Suite (`scripts/verify_step21_database.py`)**:
    * Extension & Schema: Verified active `vector` extension (0.8.0), `document_chunks` table existence, all 17 columns, and unique constraint.
    * Provenance Fidelity: Verified all 4 ingested rows match `chunks.json` byte-for-byte across verbatim text, character offsets, SHA-256 hashes, component IDs, and revisions.
    * Restart Persistence: Restarted container via `docker compose restart db`; verified all 4 rows and vector indexes survived restart intact on named volume.
    * Idempotency: Re-ran batch ingestion; verified database maintained exactly 4 rows with zero duplicates.
    * Cosine Distance Queries: Queried nearest neighbors using real 384-dim query vectors; correctly matched "Physical Dimensions Query" to Chunk 3 (similarity 0.5112) and "Product Overview Query" to Chunk 2 (similarity 0.6599).
    * Metadata Filtering: Verified SQL `WHERE` filtering on `corpus_id`, `component_id`, and `revision` correctly returns matching rows (4/4) and strictly excludes non-matching revisions, unknown component IDs, and mismatched corpora (0 rows).
    * Clear Scope Disclaimer: Labeled all checks as storage and query verification, clarifying that vector retrieval does not yet replace the deterministic investigation pipeline.
  - **Lightweight Offline Tests & CI Integration (`tests/test_database.py`)**:
    * Added 6 unit tests verifying schema SQL definitions, artifact validation, dimension rejection, matrix alignment rejection, non-finite vector rejection, and graceful skipping of live database tests when Docker/PostgreSQL is offline.
    * All 21 unit tests in `tests/` pass in 0.067s.
- [x] **Step 22: Integrate Metadata-Filtered Vector Evidence Retrieval** — Completed.
  - **Goal & Scope**: Integrate metadata-filtered vector evidence retrieval from PostgreSQL/pgvector into the investigation workflow without weakening component identity, revision, conflict detection, citation provenance, or deterministic arithmetic checks. Keep baseline document retrieval as the default for CLI and API. Separate retriever selection from extractor selection.
  - **Pluggable Retriever Architecture (`scripts/retrievers.py`)**:
    * Defined `BaseRetriever` abstract contract and factory function `get_retriever(name)`.
    * Implemented `BaselineRetriever`: fast in-memory document matching and section scanning over `data/extracted/`.
    * Implemented `PgVectorRetriever`: PostgreSQL/pgvector semantic retrieval with metadata filtering.
    * Separate selection: decoupled retriever selection (`baseline` vs. `pgvector`) from extractor selection (`deterministic` vs. `gemini`).
  - **Query Formulation & Metadata Filtering**:
    * Generates query embedding using pinned `sentence-transformers/all-MiniLM-L6-v2` (`1110a243fdf4706b3f48f1d95db1a4f5529b4d41`, 384 dimensions, normalized, CPU inference).
    * Builds queries strictly from record identity and requested attribute: `Component {component_id} {attribute_name} physical dimension parameter specification`. Never uses expected answers or target values.
    * Uses parameterized SQL with strict filtering on `(corpus_id, component_id, revision, model_name, model_revision)` before ranking.
    * Exact cosine ranking (`vector_cosine_ops`) with deterministic tie-breaking (`ORDER BY distance ASC, page_number ASC, start_char ASC, chunk_id ASC`).
  - **Safety & Conflict Detection Preserved**:
    * Full-Context Inspection: Inspects all eligible candidate chunks for the component and revision before taking top-k. If competing measurements exist for the attribute, immediately returns `ambiguous_evidence`, preventing false positives.
    * Early Abstention: Missing component IDs, unknown components, or unconfirmed revisions safely return `insufficient_evidence`.
  - **Citation Preservation & Provenance**:
    * Returns citation-preserving chunk spans (`context_type: "chunk"`), retaining verbatim text, document filename, and 1-based page coordinates.
    * Downstream validation guardrails verify verbatim grounding and apply Python `Decimal` arithmetic for exact unit conversion without LLM math.
  - **Error Handling & Password Sanitization**:
    * Catches database connection and query errors, returning structured metadata (`error_type: "DATABASE_ERROR"` or `"CONFIGURATION_ERROR"`).
    * Password sanitization masks credentials (`password=***`) to prevent secret leakage.
    * Never silently falls back to baseline when pgvector is explicitly requested.
  - **Evaluation Corpora Ingestion (`scripts/index_evaluation_corpora.py`)**:
    * Indexed all 16 evaluation cases (10 baseline + 6 challenge) and default supplier corpus into `copilot_db.document_chunks` under isolated corpus IDs (`eval-<case_name>`).
    * Ingested 68 total chunks in 0.59s.
  - **FastAPI API Integration (`api/main.py`)**:
    * Accepts `retriever` query parameter (`?retriever=baseline` or `?retriever=pgvector`) and request payload field.
    * Returns HTTP 422 for invalid retriever (`INVALID_RETRIEVER`).
    * Maps retriever configuration failures to HTTP 503 (`RETRIEVER_NOT_CONFIGURED`) and database service failures to HTTP 502 (`RETRIEVER_SERVICE_ERROR`).
    * Implemented dependency injection hook `get_retriever_dependency` for offline testing.
  - **Retriever Comparative Benchmark (`scripts/evaluate.py`)**:
    * Evaluated both retrievers with deterministic extractor held constant across all 16 cases (zero Gemini calls).
    * **100% Concordance (16/16 Cases)**: Both retrievers achieved identical decision outcomes and citation validity across all cases (15/16 pass rate, with `challenge-01` failing at measurement extraction due to documented regex phrasing limitation).
    * **100% Recall@1 on Gold Evidence (9/9 Cases)**: For all 9 cases expecting evidence, pgvector ranked the ground-truth chunk at rank #1 (cosine similarity 0.7498 - 0.8292).
    * **Recall@2**: 9/9 (100.0%), **Recall@3**: 9/9 (100.0%), **MRR**: 1.000.
    * Generated `step22_retriever_comparison_report.json` and `step22_retriever_comparison_report.md`.
  - **Automated Verification & Unit Tests**:
    * `scripts/verify_step22_retrieval.py`: Automated verification suite testing all 7 Step 22 requirements.
    * `tests/test_retrievers.py`: 13 unit and integration tests (factory, query formulation, full-context conflict detection, password sanitization, API status code mapping, and live database queries).
    * All 34 tests in `tests/` pass offline in 0.088s.

