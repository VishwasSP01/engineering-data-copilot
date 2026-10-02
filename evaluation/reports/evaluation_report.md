# Synthetic Investigation Evaluation Report (Deterministic)

> **Notice**: This report represents an evaluation designed to verify evidence retrieval, unit conversion, and decision logic. It does not claim to demonstrate production accuracy.

## Executive Summary

- **Extractor Provider**: `deterministic`
- **Total Cases**: 10
- **Passed Cases**: 10/10 (100.0%)
- **Correction-Case Pass Rate**: 2/2 (100.0%)
- **Agreement-Case Pass Rate (`no_change`)**: 2/2 (100.0%)
- **Abstention-Case Pass Rate**: 6/6 (100.0%)
- **Citation Validity**: 5/5 (100.0%) — all citations verified against source PDF text
- **Median Investigation Latency**: 1.85 ms
- **Mean Investigation Latency**: 13.79 ms
- **Model Usage**: 0 calls (deterministic rule-based baseline)
- **Model Tokens & Cost**: N/A

## Detailed Per-Case Results

| Case ID | Category | Expected Outcome | Actual Outcome | Expected Proposal | Actual Proposal | Cit. Valid | Latency (ms) | Result |
|---|---|---|---|---|---|---|---|---|
| `case-01-correction-cm-to-mm` | correction | `correction_proposed` | `correction_proposed` | 8.0 mm | 8.0 mm | ✓ | 122.79 | **PASS** |
| `case-02-correction-mm-to-cm` | correction | `correction_proposed` | `correction_proposed` | 2.5 cm | 2.5 cm | ✓ | 2.49 | **PASS** |
| `case-03-agreement-mm` | abstention | `no_change` | `no_change` | — | — | ✓ | 1.92 | **PASS** |
| `case-04-agreement-cm` | abstention | `no_change` | `no_change` | — | — | ✓ | 1.98 | **PASS** |
| `case-05-unknown-component` | abstention | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | 1.31 | **PASS** |
| `case-06-incorrect-revision` | abstention | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | 1.41 | **PASS** |
| `case-07-missing-measurement` | abstention | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | 1.77 | **PASS** |
| `case-08-conflicting-evidence` | abstention | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ | 1.26 | **PASS** |
| `case-09-unsupported-unit` | abstention | `needs_review` | `needs_review` | — | — | ✓ | 1.97 | **PASS** |
| `case-10-malformed-measurement` | abstention | `needs_review` | `needs_review` | — | — | ✓ | 0.95 | **PASS** |

## Failure Analysis & Notes
- All 10 synthetic test cases passed all verification checks.
- Both bidirectional unit conversions (`cm` → `mm` and `mm` → `cm`) verified exact Decimal arithmetic.
- Both agreement cases (`no_change`) correctly confirmed data agreement without proposing modifications.
- All abstention categories (`insufficient_evidence`, `ambiguous_evidence`, `needs_review`) correctly abstained from proposing corrections.
- Every returned citation was verified to exist verbatim on page 1 of its respective isolated supplier PDF.

