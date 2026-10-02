# Step 14: Challenge Evaluation Report (Deterministic)

> **Scope & Purpose**: This report evaluates the investigation workflow across 6 challenging synthetic supplier datasheets featuring varied wording, tabular data with separated columns, line breaks, and distracting measurements. Step 14 improved quote alignment and measurement binding across multi-attribute labelled tuples.

## Executive Summary

- **Extractor Provider**: `deterministic`
- **Total Challenge Cases**: 6
- **Evidence Retrieval Success Rate**: 4/4 (100.0%) (for cases expecting evidence)
- **Retrieval Abstention Success Rate**: 2/2 (100.0%) (for missing/ambiguous evidence cases)
- **Combined Retrieval Accuracy**: 6/6 (100.0%)
- **Overall Pass Rate (End-to-End)**: 5/6 (83.3%)
- **Correction-Case Pass Rate**: 2/3 (66.7%)
- **Agreement-Case Pass Rate (`no_change`)**: 1/1 (100.0%)
- **Abstention-Case Pass Rate**: 2/2 (100.0%)
- **Citation Validity**: 4/4 (100.0%)
- **Median Investigation Latency**: 0.52 ms
- **Mean Investigation Latency**: 0.61 ms

## Detailed Per-Case Results

| Case ID | Category | Expected Outcome | Actual Outcome | Expected Proposal | Actual Proposal | Retrieval | Cit. Valid | Result | Failure Stage |
|---|---|---|---|---|---|---|---|---|---|
| `challenge-01-complete-sentence` | challenge_sentence | `correction_proposed` | `needs_review` | 12.0 mm | — | ✓ | ✓ | **FAIL** | measurement extraction |
| `challenge-02-table-value-unit-columns` | challenge_table | `correction_proposed` | `correction_proposed` | 1.5 cm | 1.5 cm | ✓ | ✓ | **PASS** | — |
| `challenge-03-split-lines-label-measurement` | challenge_split_lines | `correction_proposed` | `correction_proposed` | 0.24 cm | 0.24 cm | ✓ | ✓ | **PASS** | — |
| `challenge-04-distracting-measurements` | challenge_distracting | `no_change` | `no_change` | — | — | ✓ | ✓ | **PASS** | — |
| `challenge-05-incorrect-revision` | challenge_revision | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | ✓ | **PASS** | — |
| `challenge-06-conflicting-statements` | challenge_conflict | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ | ✓ | **PASS** | — |

## Failure Stage & Limitation Analysis

### `challenge-01-complete-sentence`
- **Expected Outcome**: `correction_proposed` | **Actual Outcome**: `needs_review`
- **Responsible Stage**: `measurement extraction`
- **Limitation Explanation**: Retrieval succeeded in extracting the verbatim physical dimensions section. The deterministic regex extractor failed because interstitial sentence phrasing ('of component COMP-C01 is') led to extracting unit 'is', triggering unit guardrails.

## Passed Cases

- **`challenge-02-table-value-unit-columns`**: Correctly returned `correction_proposed`. Multi-column table cells are extracted by pypdf as individual separate lines ('Thickness\n15.0\nmm'). Line-by-line scanning cannot correlate the attribute name with values and units located in subsequent table lines.
- **`challenge-03-split-lines-label-measurement`**: Correctly returned `correction_proposed`. Retrieval splits extracted page text strictly on newlines and processes each line in isolation. When an attribute label and its numeric measurement are wrapped across a newline, neither line individually matches candidate extraction.
- **`challenge-04-distracting-measurements`**: Correctly returned `no_change`. Candidate passage regex matches the nearest numeric token following 'thickness' (which matches the adjacent length '60.0 mm' after the closing parenthesis). As a result, the pipeline extracts the wrong dimension (60.0 mm instead of 6.0 mm) and proposes an incorrect correction (6.0 cm) instead of no_change.
- **`challenge-05-incorrect-revision`**: Correctly returned `insufficient_evidence`. Expected behavior: Revision guardrail correctly identifies revision mismatch and safely abstains with insufficient_evidence.
- **`challenge-06-conflicting-statements`**: Correctly returned `ambiguous_evidence`. Expected behavior: Ambiguity resolution guardrail detects multiple distinct thickness measurements and safely abstains with ambiguous_evidence.

## Conclusion & Measurement Binding Improvement Summary
- **Evidence Retrieval vs. Abstention**: Evidence retrieval achieved **4/4 (100.0%)** on cases expecting evidence, and retrieval abstention achieved **2/2 (100.0%)** on cases with missing or ambiguous evidence, verifying that retrieval was decoupled from measurement parsing without weakening component or revision guardrails.
- **End-to-End Pass Rate**: The deterministic pipeline achieved **5/6 (83.3%)** (an increase of 16.7 percentage points from 4/6 [66.7%] in Step 12, and 50.0 percentage points from 2/6 [33.3%] in Step 11).
- **Resolved Cases**: Labelled tuple parsing resolved `challenge-04-distracting-measurements` by correctly binding the target attribute ('thickness') to its 3rd position in '(length, width, thickness): 60 mm x 40 mm x 6 mm' rather than greedily taking the first value.
- **Remaining Deterministic Limitations**: Only 1 case (`challenge-01-complete-sentence`) remains failing deterministically, where regex cannot parse the interstitial sentence structure.

