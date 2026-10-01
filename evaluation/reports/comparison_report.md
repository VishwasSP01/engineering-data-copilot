# Step 10: Provider Comparison Report (Deterministic vs. Live Gemini)

> **Scope & Limitations**: This report evaluates the deterministic rule-based extractor against live `gemini-3.5-flash-lite` across an identical 10-case synthetic evaluation suite. **All findings are strictly limited to these 10 synthetic cases and do not claim to demonstrate generalization or accuracy across real-world supplier documents.**

## Executive Summary

| Metric | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Comparison |
|---|---|---|---|
| **Overall Pass Rate** | 10/10 (100.0%) | 10/10 (100.0%) | Identical |
| **Correction Cases Pass Rate** | 2/2 (100.0%) | 2/2 (100.0%) | Identical |
| **Agreement Cases Pass Rate (`no_change`)** | 2/2 (100.0%) | 2/2 (100.0%) | Identical |
| **Abstention Cases Pass Rate** | 6/6 (100.0%) | 6/6 (100.0%) | Identical |
| **Citation Validity** | 5/5 (100.0%) | 5/5 (100.0%) | Identical |
| **API Errors / Failures** | 0/10 (0.0%) | 0/10 (0.0%) | — |
| **Unrun Cases** | 0/10 (0.0%) | 0/10 (0.0%) | — |
| **Model Calls Attempted** | 0/10 | 5/10 | — |
| **Model Calls Succeeded** | 0/0 | 5/5 | — |
| **Cases Without Model Call** | 10/10 (100.0%) | 5/10 | Retrieval checks preserved |
| **Median Latency (All 10 Cases)** | 0.63 ms | 381.38 ms | Deterministic is faster |
| **Median Latency (Model-Called Cases, 5 Cases)** | 0.84 ms | 791.92 ms | Network API call overhead |
| **Median Latency (Non-Model Cases, 5 Cases)** | 0.57 ms | 0.32 ms | Local early abstention |
| **Token Usage** | 0 tokens | 1241 total | — |
| **Estimated Cost** | $0.00 | null (unestimated) | Pricing external to API metadata |

- **Concordance Between Providers**: **10/10 (100.0%)**

## Detailed Per-Case Comparison

| Case ID | Category | Expected Outcome | Deterministic | Gemini | Model Called? | Tokens | Det Lat (ms) | Gem Lat (ms) | Agreement |
|---|---|---|---|---|---|---|---|---|---|
| `case-01-correction-cm-to-mm` | correction | `correction_proposed` | `correction_proposed` | `correction_proposed` | Yes | 247t | 1.53 | 953.6 | ✓ Match |
| `case-02-correction-mm-to-cm` | correction | `correction_proposed` | `correction_proposed` | `correction_proposed` | Yes | 250t | 1.22 | 791.92 | ✓ Match |
| `case-03-agreement-mm` | agreement | `no_change` | `no_change` | `no_change` | Yes | 247t | 0.55 | 762.31 | ✓ Match |
| `case-04-agreement-cm` | agreement | `no_change` | `no_change` | `no_change` | Yes | 250t | 0.84 | 763.61 | ✓ Match |
| `case-05-unknown-component` | abstention | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | No | — | 0.68 | 0.45 | ✓ Match |
| `case-06-incorrect-revision` | abstention | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | No | — | 0.65 | 0.29 | ✓ Match |
| `case-07-missing-measurement` | abstention | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | No | — | 0.52 | 0.32 | ✓ Match |
| `case-08-conflicting-evidence` | abstention | `ambiguous_evidence` | `ambiguous_evidence` | `ambiguous_evidence` | No | — | 0.57 | 0.35 | ✓ Match |
| `case-09-unsupported-unit` | abstention | `needs_review` | `needs_review` | `needs_review` | Yes | 247t | 0.61 | 908.54 | ✓ Match |
| `case-10-malformed-measurement` | abstention | `needs_review` | `needs_review` | `needs_review` | No | — | 0.25 | 0.18 | ✓ Match |

## Comparative Analysis & Findings

1. **Performance Parity**: Live `gemini-3.5-flash-lite` achieved an overall pass rate of **10/10 (100.0%)**, matching the deterministic baseline (**10/10 (100.0%)**). Across all 10 synthetic benchmark cases, Gemini **matched** the baseline without improving or degrading decision quality:
   - **Correction Cases**: 2/2 (100.0%) on both providers.
   - **Agreement Cases (`no_change`)**: 2/2 (100.0%) on both providers.
   - **Abstention Cases**: 6/6 (100.0%) on both providers (`insufficient_evidence`, `ambiguous_evidence`, `needs_review`).
2. **Early Retrieval Abstention (Safety Preservation)**: In 5 out of 10 cases (unknown component, incorrect revision, missing attribute, conflicting measurements, and malformed record value), retrieval or record validation safely aborted before calling Gemini. This confirmed that retrieval boundary checks successfully prevented unnecessary model invocation and API spend.
3. **Downstream Arithmetic Integrity**: In all cases where Gemini extracted measurement values, unit conversions were computed exclusively using deterministic Python `Decimal` arithmetic, guaranteeing exact numerical accuracy without LLM calculation errors.
4. **Latency Profile**:
   - **All 10 Cases**: Deterministic median latency was **0.63 ms** (mean: 0.74 ms), whereas Gemini's all-case median latency was **381.38 ms** (mean: 418.16 ms).
   - **Model-Called Cases (5 Cases)**: For cases invoking the API (cases 1, 2, 3, 4, 9), Gemini median latency was **791.92 ms** (mean: 836.00 ms; range 762.31–953.60 ms) due to network transit and model generation, compared to **0.84 ms** (mean: 0.95 ms) for the deterministic regex baseline.
   - **Non-Model Cases (5 Cases)**: For early abstention cases (cases 5, 6, 7, 8, 10), both providers executed locally with sub-millisecond median latencies (**0.57 ms** deterministic vs. **0.32 ms** Gemini).

## Limitations Notice
- All cases in this benchmark are synthetic demonstration documents with uniform typography and structure.
- These results do not guarantee model extraction accuracy on real-world engineering documents containing complex tables, multi-column layouts, scan artifacts, or conflicting drawing notes.
