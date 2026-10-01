# Step 11: Challenge Evaluation Report (Deterministic)

> **Scope & Purpose**: This report evaluates the deterministic workflow across 6 challenging synthetic supplier datasheets featuring varied wording, tabular data with separated columns, line breaks, and distracting measurements. The objective is to identify and document current baseline limitations without modifying existing retrieval or extraction code.

## Executive Summary

- **Extractor Provider**: `deterministic`
- **Total Challenge Cases**: 6
- **Overall Pass Rate**: 2/6 (33.3%)
- **Correction-Case Pass Rate**: 0/3 (0.0%)
- **Agreement-Case Pass Rate (`no_change`)**: 0/1 (0.0%)
- **Abstention-Case Pass Rate**: 2/2 (100.0%)
- **Citation Validity**: 1/4 (25.0%)
- **Median Investigation Latency**: 0.38 ms
- **Mean Investigation Latency**: 0.53 ms

## Detailed Per-Case Results

| Case ID | Category | Expected Outcome | Actual Outcome | Expected Proposal | Actual Proposal | Cit. Valid | Result | Failure Stage |
|---|---|---|---|---|---|---|---|---|
| `challenge-01-complete-sentence` | challenge_sentence | `correction_proposed` | `needs_review` | 12.0 mm | — | ✗ | **FAIL** | retrieval |
| `challenge-02-table-value-unit-columns` | challenge_table | `correction_proposed` | `insufficient_evidence` | 1.5 cm | — | ✗ | **FAIL** | retrieval |
| `challenge-03-split-lines-label-measurement` | challenge_split_lines | `correction_proposed` | `insufficient_evidence` | 0.24 cm | — | ✗ | **FAIL** | retrieval |
| `challenge-04-distracting-measurements` | challenge_distracting | `no_change` | `correction_proposed` | — | 6.0 cm | ✓ | **FAIL** | retrieval |
| `challenge-05-incorrect-revision` | challenge_revision | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | **PASS** | — |
| `challenge-06-conflicting-statements` | challenge_conflict | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ | **PASS** | — |

## Failure Stage & Limitation Analysis

### `challenge-01-complete-sentence`
- **Expected Outcome**: `correction_proposed` | **Actual Outcome**: `needs_review`
- **Responsible Stage**: `retrieval`
- **Limitation Explanation**: Line-based candidate passage regex expects an immediate delimiter (':', '=', or 'is') followed directly by the number; descriptive sentences containing interstitial phrases (e.g. 'is manufactured to 1.2 cm') fail candidate extraction.

### `challenge-02-table-value-unit-columns`
- **Expected Outcome**: `correction_proposed` | **Actual Outcome**: `insufficient_evidence`
- **Responsible Stage**: `retrieval`
- **Limitation Explanation**: Multi-column table cells are extracted by pypdf as individual separate lines ('Thickness\n15.0\nmm'). Line-by-line scanning cannot correlate the attribute name with values and units located in subsequent table lines.

### `challenge-03-split-lines-label-measurement`
- **Expected Outcome**: `correction_proposed` | **Actual Outcome**: `insufficient_evidence`
- **Responsible Stage**: `retrieval`
- **Limitation Explanation**: Retrieval splits extracted page text strictly on newlines and processes each line in isolation. When an attribute label and its numeric measurement are wrapped across a newline, neither line individually matches candidate extraction.

### `challenge-04-distracting-measurements`
- **Expected Outcome**: `no_change` | **Actual Outcome**: `correction_proposed`
- **Responsible Stage**: `retrieval`
- **Limitation Explanation**: Candidate passage regex matches the nearest numeric token following 'thickness' (which matches the adjacent length '60.0 mm' after the closing parenthesis). As a result, the pipeline extracts the wrong dimension (60.0 mm instead of 6.0 mm) and proposes an incorrect correction (6.0 cm) instead of no_change.

## Passed Guardrail Cases

- **`challenge-05-incorrect-revision`**: Correctly returned `insufficient_evidence`. Expected behavior: Revision guardrail correctly identifies revision mismatch and safely abstains with insufficient_evidence.
- **`challenge-06-conflicting-statements`**: Correctly returned `ambiguous_evidence`. Expected behavior: Ambiguity resolution guardrail detects multiple distinct thickness measurements and safely abstains with ambiguous_evidence.

## Conclusion & Baseline Limitations Summary
- **Pass Rate**: The deterministic baseline passed **2/6 (33.3%)** challenge cases, successfully honoring revision isolation and conflict abstention guardrails.
- **Root Cause of Failures**: All 4 failure cases failed at the **retrieval** stage due to rigid line-by-line scanning and localized regex pattern assumptions (inability to correlate wrapped table cells, multi-line labels, complete sentences with interstitial phrasing, or disambiguate concatenated dimensional tokens).
- **Benchmark Persistence**: These 6 challenge cases are retained as a permanent, fixed evaluation suite for subsequent comparison against LLM-based extractors.

