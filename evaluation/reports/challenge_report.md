# Step 12: Challenge Evaluation Report (Deterministic)

> **Scope & Purpose**: This report evaluates the investigation workflow across 6 challenging synthetic supplier datasheets featuring varied wording, tabular data with separated columns, line breaks, and distracting measurements. Step 12 improved evidence retrieval by decoupling evidence discovery from measurement parsing and introducing section/page fallback.

## Executive Summary

- **Extractor Provider**: `deterministic`
- **Total Challenge Cases**: 6
- **Retrieval Success Rate**: 6/6 (100.0%)
- **Overall Pass Rate (End-to-End)**: 4/6 (66.7%)
- **Correction-Case Pass Rate**: 2/3 (66.7%)
- **Agreement-Case Pass Rate (`no_change`)**: 0/1 (0.0%)
- **Abstention-Case Pass Rate**: 2/2 (100.0%)
- **Citation Validity**: 4/4 (100.0%)
- **Median Investigation Latency**: 0.46 ms
- **Mean Investigation Latency**: 0.56 ms

## Detailed Per-Case Results

| Case ID | Category | Expected Outcome | Actual Outcome | Expected Proposal | Actual Proposal | Retrieval | Cit. Valid | Result | Failure Stage |
|---|---|---|---|---|---|---|---|---|---|
| `challenge-01-complete-sentence` | challenge_sentence | `correction_proposed` | `needs_review` | 12.0 mm | — | ✓ | ✓ | **FAIL** | measurement extraction |
| `challenge-02-table-value-unit-columns` | challenge_table | `correction_proposed` | `correction_proposed` | 1.5 cm | 1.5 cm | ✓ | ✓ | **PASS** | — |
| `challenge-03-split-lines-label-measurement` | challenge_split_lines | `correction_proposed` | `correction_proposed` | 0.24 cm | 0.24 cm | ✓ | ✓ | **PASS** | — |
| `challenge-04-distracting-measurements` | challenge_distracting | `no_change` | `correction_proposed` | — | 6.0 cm | ✓ | ✓ | **FAIL** | measurement extraction |
| `challenge-05-incorrect-revision` | challenge_revision | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | ✓ | **PASS** | — |
| `challenge-06-conflicting-statements` | challenge_conflict | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ | ✓ | **PASS** | — |

## Failure Stage & Limitation Analysis

### `challenge-01-complete-sentence`
- **Expected Outcome**: `correction_proposed` | **Actual Outcome**: `needs_review`
- **Responsible Stage**: `measurement extraction`
- **Limitation Explanation**: Retrieval succeeded in extracting the verbatim physical dimensions section. The deterministic regex extractor failed because interstitial sentence phrasing ('of component COMP-C01 is') led to extracting unit 'is', triggering unit guardrails.

### `challenge-04-distracting-measurements`
- **Expected Outcome**: `no_change` | **Actual Outcome**: `correction_proposed`
- **Responsible Stage**: `measurement extraction`
- **Limitation Explanation**: Retrieval succeeded in extracting the verbatim dimensions section. The deterministic regex extractor failed because it greedily extracted the adjacent length dimension ('60.0 mm') after the attribute keyword instead of thickness ('6.0 mm').

## Passed Cases

- **`challenge-02-table-value-unit-columns`**: Correctly returned `correction_proposed`. Multi-column table cells are extracted by pypdf as individual separate lines ('Thickness\n15.0\nmm'). Line-by-line scanning cannot correlate the attribute name with values and units located in subsequent table lines.
- **`challenge-03-split-lines-label-measurement`**: Correctly returned `correction_proposed`. Retrieval splits extracted page text strictly on newlines and processes each line in isolation. When an attribute label and its numeric measurement are wrapped across a newline, neither line individually matches candidate extraction.
- **`challenge-05-incorrect-revision`**: Correctly returned `insufficient_evidence`. Expected behavior: Revision guardrail correctly identifies revision mismatch and safely abstains with insufficient_evidence.
- **`challenge-06-conflicting-statements`**: Correctly returned `ambiguous_evidence`. Expected behavior: Ambiguity resolution guardrail detects multiple distinct thickness measurements and safely abstains with ambiguous_evidence.

## Conclusion & Retrieval Improvement Summary
- **Retrieval Decoupling**: Evidence retrieval achieved **6/6 (100.0%)**, successfully finding relevant section context across complex table, sentence, and wrapped layouts without weakening component or revision guardrails.
- **End-to-End Pass Rate**: The deterministic pipeline achieved **4/6 (66.7%)** (up from 2/6 in Step 11).
- **Failure Stage Shift**: All remaining failures shifted from `retrieval` to `measurement extraction`, where the baseline regex extractor cannot handle interstitial sentence prose (`challenge-01`) or disambiguate concatenated multi-dimension lists (`challenge-04`).

