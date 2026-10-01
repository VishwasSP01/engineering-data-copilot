# Synthetic Investigation Evaluation Report

> **Notice**: This report represents a small synthetic evaluation suite designed to verify deterministic evidence retrieval, unit conversion, and decision logic. It does not claim to demonstrate production accuracy.

## Executive Summary

- **Total Cases**: 10
- **Passed Cases**: 10 / 10 (100.0%)
- **Correction-Case Pass Rate**: 100.0% (2 cases)
- **Abstention-Case Pass Rate**: 100.0% (8 cases)
- **Citation Validity**: 5/5 (100.0%) — all citations verified against source PDF text
- **Median Investigation Latency**: 0.44 ms
- **Mean Investigation Latency**: 0.55 ms
- **Model Usage**: 0 calls (deterministic rule-based baseline)
- **Model Tokens & Cost**: N/A

## Detailed Per-Case Results

| Case ID | Category | Expected Outcome | Actual Outcome | Expected Proposal | Actual Proposal | Cit. Valid | Latency (ms) | Result |
|---|---|---|---|---|---|---|---|---|
| `case-01-correction-cm-to-mm` | correction | `correction_proposed` | `correction_proposed` | 8.0 mm | 8.0 mm | ✓ | 1.37 | **PASS** |
| `case-02-correction-mm-to-cm` | correction | `correction_proposed` | `correction_proposed` | 2.5 cm | 2.5 cm | ✓ | 1.11 | **PASS** |
| `case-03-agreement-mm` | abstention | `no_change` | `no_change` | — | — | ✓ | 0.46 | **PASS** |
| `case-04-agreement-cm` | abstention | `no_change` | `no_change` | — | — | ✓ | 0.43 | **PASS** |
| `case-05-unknown-component` | abstention | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | 0.49 | **PASS** |
| `case-06-incorrect-revision` | abstention | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | 0.46 | **PASS** |
| `case-07-missing-measurement` | abstention | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ | 0.37 | **PASS** |
| `case-08-conflicting-evidence` | abstention | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ | 0.37 | **PASS** |
| `case-09-unsupported-unit` | abstention | `needs_review` | `needs_review` | — | — | ✓ | 0.39 | **PASS** |
| `case-10-malformed-measurement` | abstention | `needs_review` | `needs_review` | — | — | ✓ | 0.07 | **PASS** |

## Failure Analysis & Notes
- All 10 synthetic test cases passed all verification checks without regression.
- Both bidirectional unit conversions (`cm` → `mm` and `mm` → `cm`) verified exact Decimal arithmetic.
- All abstention categories (`no_change`, `insufficient_evidence`, `ambiguous_evidence`, `needs_review`) correctly abstained from proposing corrections.
- Every returned citation was verified to exist verbatim on page 1 of its respective isolated supplier PDF.

