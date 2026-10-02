# Step 15: Challenge Comparison Report (Deterministic vs. Live Gemini)

> **Scope & Limitations**: This report evaluates the deterministic rule-based extractor against live `gemini-3.5-flash-lite` across the 6 challenging synthetic supplier datasheets (sentence, table columns, split lines, distracting dimensions, revision mismatch, and conflicting statements) following the Step 14 quote alignment and labelled measurement binding improvements. **All findings are strictly limited to these 6 synthetic test fixtures.**

## Benchmark Configuration & Frozen Versions

- **Git Commit**: `cfcbbda5b5df1a915a2e074caf015a3fbd34f4be`
- **Configured Model**: `gemini-3.5-flash-lite` (automatic retries disabled, max attempts = 1)
- **Evaluation Fixtures**: `evaluation/cases/ (6 isolated synthetic challenge cases)`
- **Expected Answers**: `evaluation/expected/ (frozen expected JSONs)`
- **Retrieval Logic**: `scripts/retrieve_evidence.py (decoupled retrieval with verbatim section/page fallback)`
- **Extraction Prompt**: `scripts/extractors.py:build_extraction_prompt (strict boundary extraction)`
- **Validation Implementation**: `scripts/investigate_record.py (whitespace-aware quote alignment & tuple parsing)`

## Executive Summary

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Comparison |
|---|---|---|---|
| **Overall Pass Rate (End-to-End)** | 5/6 (83.3%) | 6/6 (100.0%) | **Gemini Higher (+16.7 percentage points)** |
| **Evidence Retrieval Success Rate** | 4/4 (100.0%) | 4/4 (100.0%) | Identical (100.0%) |
| **Retrieval Abstention Success Rate** | 2/2 (100.0%) | 2/2 (100.0%) | Identical (100.0%) |
| **Combined Retrieval Accuracy** | 6/6 (100.0%) | 6/6 (100.0%) | Identical (100.0%) |
| **Correction-Case Pass Rate** | 2/3 (66.7%) | 3/3 (100.0%) | Gemini Higher |
| **Agreement-Case Pass Rate (`no_change`)** | 1/1 (100.0%) | 1/1 (100.0%) | Identical |
| **Abstention-Case Pass Rate** | 2/2 (100.0%) | 2/2 (100.0%) | Identical |
| **Citation Validity** | 4/4 (100.0%) | 4/4 (100.0%) | Identical |
| **API Errors / Failures** | 0/6 (0.0%) | 0/6 (0.0%) | — |
| **Unrun Cases** | 0/6 (0.0%) | 0/6 (0.0%) | — |
| **Model Requests Attempted** | 0/6 | 4/6 | At most 6 requests |
| **Model Requests Completed** | 0/0 | 4/4 | Zero retries |
| **Cases Without Model Call (Skipped)** | 6/6 (100.0%) | 2/6 | Retrieval early abstention |
| **Median Latency (All 6 Cases)** | 0.48 ms | 813.33 ms | Deterministic is faster |
| **Median Latency (Model-Called Cases)** | N/A | 880.62 ms | Network transit overhead |
| **Median Latency (Non-Model Cases)** | 0.48 ms | 0.23 ms | Local early abstention |
| **Token Usage** | 0 tokens | 1395 total (1142 prompt, 253 candidate) | — |
| **Estimated Cost** | $0.00 | null (unestimated) | Pricing external to API metadata |

- **Provider Concordance**: **5/6 (83.3%)**

## Detailed Per-Case Comparison

| Case ID | Category | Expected Outcome | Deterministic Outcome | Gemini Outcome | Retrieval | Model Called | Det Result | Gem Result | Agreement | Det Failure Stage | Gem Failure Stage |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `challenge-01-complete-sentence` | challenge_sentence | `correction_proposed` | `needs_review` | `correction_proposed` | ✓ | Yes | **FAIL** | **PASS** | ✗ Mismatch | measurement extraction | — |
| `challenge-02-table-value-unit-columns` | challenge_table | `correction_proposed` | `correction_proposed` | `correction_proposed` | ✓ | Yes | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-03-split-lines-label-measurement` | challenge_split_lines | `correction_proposed` | `correction_proposed` | `correction_proposed` | ✓ | Yes | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-04-distracting-measurements` | challenge_distracting | `no_change` | `no_change` | `no_change` | ✓ | Yes | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-05-incorrect-revision` | challenge_revision | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | ✓ | No | **PASS** | **PASS** | ✓ Match | — | — |
| `challenge-06-conflicting-statements` | challenge_conflict | `ambiguous_evidence` | `ambiguous_evidence` | `ambiguous_evidence` | ✓ | No | **PASS** | **PASS** | ✓ Match | — | — |

## Comparative Analysis: Value Added by Gemini Extractor

### Where Gemini Improved Results
- **`challenge-01-complete-sentence`**: Deterministic failed at `measurement extraction`, whereas Gemini successfully passed with `correction_proposed`.
  * Deterministic limitation: Retrieval succeeded in extracting the verbatim physical dimensions section. The deterministic regex extractor failed because interstitial sentence phrasing ('of component COMP-C01 is') led to extracting unit 'is', triggering unit guardrails.
  * Gemini resolution: Correctly extracted target measurement from retrieved section.

### Where Gemini Matched the Baseline
- **`challenge-02-table-value-unit-columns`**: Both passed (`correction_proposed`).
- **`challenge-03-split-lines-label-measurement`**: Both passed (`correction_proposed`).
- **`challenge-04-distracting-measurements`**: Both passed (`no_change`).
- **`challenge-05-incorrect-revision`**: Both passed (`insufficient_evidence`).
  * Early abstention preserved: Retrieval yielded insufficient_evidence; extractor not invoked..
- **`challenge-06-conflicting-statements`**: Both passed (`ambiguous_evidence`).
  * Early abstention preserved: Retrieval yielded ambiguous_evidence; extractor not invoked..

### Regressions
- **Zero Regressions**: Gemini did not degrade or worsen any case that the deterministic extractor passed.

## Evolution Across Steps: Step 13 Live vs. Step 14 Replay vs. Step 15 Live

| Step | Evaluation Type | Deterministic Pass Rate | Gemini Pass Rate | `challenge-01` (Sentence) | `challenge-04` (Tuple) | Key Finding |
|---|---|---|---|---|---|---|
| **Step 13** | Live API Call | 4 / 6 (66.7%) | 5 / 6 (83.3%) | Gemini FAIL (validation whitespace) | Gemini PASS (`no_change`) | Gemini resolved tuple disambiguation; whitespace line-break triggered strict quote rejection |
| **Step 14** | Offline Replay | 5 / 6 (83.3%) | 6 / 6 (100.0%) [Replay] | Replay PASS (whitespace aligned) | Det PASS (tuple parsed) | Token index mapping aligned quote offline; labelled tuple parsed deterministically |
| **Step 15** | Live API Call | 5/6 (83.3%) | 6/6 (100.0%) | Gemini PASS (live) | Gemini PASS (live) | Fresh live verification with automatic retries disabled |

## Failure Stage & Validation Rejection Analysis

### Validation Guardrails
- No model extractions were rejected by downstream validation guardrails.

## Resource & Latency Profile
- **Deterministic Baseline**: Median investigation duration was **0.48 ms** (sub-millisecond local execution).
- **Gemini Provider**: Median investigation duration across all cases was **813.33 ms**.
- **Model-Called Cases**: Median call latency was **880.62 ms** across 4/4 API requests.
- **Non-Model Cases**: Median latency for early abstentions was **0.23 ms**, confirming that retrieval guardrails avert unnecessary model latency.

## Limitations Notice
- All challenge cases represent isolated synthetic PDF documents.
- These results demonstrate model reasoning capability on diverse layouts (sentences, multi-column tables, line breaks, distracting dimensions) under controlled test conditions, but do not imply production guarantees across unconstrained real-world supplier documents.

