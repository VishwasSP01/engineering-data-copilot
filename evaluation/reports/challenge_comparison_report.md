# Step 13: Challenge Comparison Report (Deterministic vs. Live Gemini)

> **Scope & Limitations**: This report evaluates the deterministic rule-based extractor against live `gemini-3.5-flash-lite` across the 6 challenging synthetic supplier datasheets (sentence, table columns, split lines, distracting dimensions, revision mismatch, and conflicting statements) following the Step 12 retrieval improvement. **All findings are strictly limited to these 6 synthetic test fixtures.**

## Executive Summary

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Comparison |
|---|---|---|---|
| **Overall Pass Rate (End-to-End)** | 4/6 (66.7%) | 5/6 (83.3%) | **Gemini Improved** |
| **Retrieval Success Rate** | 6/6 (100.0%) | 6/6 (100.0%) | Identical (100.0%) |
| **Correction-Case Pass Rate** | 2/3 (66.7%) | 2/3 (66.7%) | Identical |
| **Agreement-Case Pass Rate (`no_change`)** | 0/1 (0.0%) | 1/1 (100.0%) | Gemini Higher |
| **Abstention-Case Pass Rate** | 2/2 (100.0%) | 2/2 (100.0%) | Identical |
| **Citation Validity** | 4/4 (100.0%) | 4/4 (100.0%) | Identical |
| **API Errors / Failures** | 0/6 (0.0%) | 0/6 (0.0%) | — |
| **Unrun Cases** | 0/6 (0.0%) | 0/6 (0.0%) | — |
| **Model Requests Attempted** | 0/6 | 4/6 | At most 6 requests |
| **Model Requests Completed** | 0/0 | 4/4 | Zero retries |
| **Cases Without Model Call (Skipped)** | 6/6 (100.0%) | 2/6 | Retrieval early abstention |
| **Median Latency (All 6 Cases)** | 0.46 ms | 821.71 ms | Deterministic is faster |
| **Median Latency (Model-Called Cases)** | N/A | 872.17 ms | Network transit overhead |
| **Median Latency (Non-Model Cases)** | 0.46 ms | 0.43 ms | Local early abstention |
| **Token Usage** | 0 tokens | 1395 total (1142 prompt, 253 candidate) | — |
| **Estimated Cost** | $0.00 | null (unestimated) | Pricing external to API metadata |

- **Provider Concordance**: **5/6 (83.3%)**

## Detailed Per-Case Comparison

| Case ID | Category | Expected Outcome | Deterministic Outcome | Gemini Outcome | Retrieval | Model Called | Det Result | Gem Result | Agreement | Det Failure Stage | Gem Failure Stage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `challenge-01-complete-sentence` | challenge_sentence | `correction_proposed` | `needs_review` | `needs_review` | ✓ | Yes | **FAIL** | **FAIL** | ✓ Match | measurement extraction | validation |
| `challenge-02-table-value-unit-columns` | challenge_table | `correction_proposed` | `correction_proposed` | `correction_proposed` | ✓ | Yes | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-03-split-lines-label-measurement` | challenge_split_lines | `correction_proposed` | `correction_proposed` | `correction_proposed` | ✓ | Yes | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-04-distracting-measurements` | challenge_distracting | `no_change` | `correction_proposed` | `no_change` | ✓ | Yes | **FAIL** | **PASS** | ✗ Mismatch | measurement extraction | — |
| `challenge-05-incorrect-revision` | challenge_revision | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | ✓ | No | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-06-conflicting-statements` | challenge_conflict | `ambiguous_evidence` | `ambiguous_evidence` | `ambiguous_evidence` | ✓ | No | **PASS** | **PASS** | ✓ Match | — | — |

## Comparative Analysis: Value Added by Gemini Extractor

### Where Gemini Improved Results
- **`challenge-04-distracting-measurements`**: Deterministic failed at `measurement extraction`, whereas Gemini successfully passed with `no_change`.
  * Deterministic limitation: Retrieval succeeded in extracting the verbatim dimensions section. The deterministic regex extractor failed because it greedily extracted the adjacent length dimension ('60.0 mm') after the attribute keyword instead of thickness ('6.0 mm').
  * Gemini resolution: Correctly extracted target measurement from retrieved section.

### Where Gemini Matched the Baseline
- **`challenge-01-complete-sentence`**: Both failed (`needs_review`).
- **`challenge-02-table-value-unit-columns`**: Both passed (`correction_proposed`).
- **`challenge-03-split-lines-label-measurement`**: Both passed (`correction_proposed`).
- **`challenge-05-incorrect-revision`**: Both passed (`insufficient_evidence`).
  * Early abstention preserved: Retrieval yielded insufficient_evidence; extractor not invoked..
- **`challenge-06-conflicting-statements`**: Both passed (`ambiguous_evidence`).
  * Early abstention preserved: Retrieval yielded ambiguous_evidence; extractor not invoked..

### Regressions
- **Zero Regressions**: Gemini did not degrade or worsen any case that the deterministic extractor passed.

## Failure Stage & Validation Rejection Analysis

### Validation Rejections of Model Extractions
- **`challenge-01-complete-sentence`**: Downstream validation guardrails rejected extraction: Ungrounded extraction: supporting quote 'the nominal thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots.' was not found verbatim in cited evidence passage.

## Resource & Latency Profile
- **Deterministic Baseline**: Median investigation duration was **0.46 ms** (sub-millisecond local execution).
- **Gemini Provider**: Median investigation duration across all cases was **821.71 ms**.
- **Model-Called Cases**: Median call latency was **872.17 ms** across 4/4 API requests.
- **Non-Model Cases**: Median latency for early abstentions was **0.43 ms**, confirming that retrieval guardrails avert unnecessary model latency.

## Limitations Notice
- All challenge cases represent isolated synthetic PDF documents.
- These results demonstrate model reasoning capability on diverse layouts (sentences, multi-column tables, line breaks, distracting dimensions) under controlled test conditions, but do not imply production guarantees across unconstrained real-world supplier documents.

