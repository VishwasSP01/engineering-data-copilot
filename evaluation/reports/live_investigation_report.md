# Step 9: Live Gemini Investigation Report

> **Notice**: This report documents a single live sample investigation (`unit-mismatch-001`) verifying end-to-end model adapter extraction, quote grounding, and deterministic Decimal conversion. **This is a single sample test, not an accuracy or performance benchmark across diverse documents.**

## Executive Summary

- **Investigation Target**: `unit-mismatch-001` (Component `COMP-001`, Rev `A`, thickness `0.8 mm`)
- **Live Provider**: `google-genai` SDK
- **Active Model**: `gemini-3.5-flash-lite`
- **Timestamp**: `2026-10-01T22:35:49+02:00`
- **Investigation Outcome**: `correction_proposed`
- **Baseline Agreement**: 100% agreement with deterministic baseline provider
- **Overall Result**: **PASS**

---

## Comparison: Deterministic Baseline vs. Live Gemini

| Dimension | Deterministic Baseline | Live Gemini (`gemini-3.5-flash-lite`) | Agreement |
|---|---|---|---|
| **Extracted Measurement** | `0.8 cm` | `0.8 cm` | ✓ Match |
| **Supporting Passage** | `"Component thickness: 0.8 cm."` | `"Component thickness: 0.8 cm."` | ✓ Match |
| **Cited Source** | `supplier-COMP-001.pdf` (p. 1) | `supplier-COMP-001.pdf` (p. 1) | ✓ Match |
| **Conversion Method** | Deterministic Decimal Arithmetic | Deterministic Decimal Arithmetic | ✓ Match |
| **Conversion Formula** | `0.8 cm * 10 mm/cm = 8.0 mm` | `0.8 cm * 10 mm/cm = 8.0 mm` | ✓ Match |
| **Proposed Correction** | `8.0 mm` | `8.0 mm` | ✓ Match |
| **Investigation Outcome** | `correction_proposed` | `correction_proposed` | ✓ Match |
| **Record Unchanged** | `source_record_modified: false` | `source_record_modified: false` | ✓ Match |
| **Call Latency** | `0.00 ms` | `965.75 ms` | — |
| **Token Usage** | N/A | 247 tokens (193 prompt, 54 candidate) | — |

---

## Independent Verification Checklist

- [x] **Model Extraction**: `gemini-3.5-flash-lite` extracted `0.8 cm` for requested attribute `thickness`.
- [x] **Quote Grounding**: Supporting quote `"Component thickness: 0.8 cm."` was confirmed verbatim in `supplier-COMP-001.pdf` page 1.
- [x] **Deterministic Conversion**: Converted via Python `Decimal` arithmetic: \( 0.8\text{ cm} \times 10 = 8.0\text{ mm} \). The model was never asked to perform arithmetic.
- [x] **Safety & Immutability**: Source engineering database record remained unmodified (`source_record_modified: false`).
- [x] **Information Isolation**: Target units and expected answers were strictly excluded from runtime prompts and model inputs.
- [x] **Execution Hygiene**: No credentials printed, logged, or included in report artifacts.

---

## Model Execution & Resource Metrics

- **Provider**: `google-genai`
- **Model Identifier**: `gemini-3.5-flash-lite`
- **HTTP Retries**: Disabled (`attempts=1`)
- **Call Duration**: 965.75 ms
- **Token Counts**:
  - Prompt tokens: 193
  - Candidate tokens: 54
  - Total tokens: 247
- **Estimated Cost**: `null` (API token pricing rates are external to SDK metadata and are not estimated here).

---

## Attempt History & Reliability Log

Prior attempts during Step 9 live verification were preserved for full transparency:

1. **Attempt 1 (`gemini-2.5-flash`)**:
   - Status: Failed (`404 NOT_FOUND`)
   - Latency: 259.87 ms
   - Error: `This model models/gemini-2.5-flash is no longer available to new users. Please update your code to use models/gemini-3.8-flash...`
2. **Attempt 2 (`gemini-3.8-flash`)**:
   - Status: Failed (`503 UNAVAILABLE`)
   - Latency: 1290.51 ms
   - Error: `This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.`
3. **Attempt 3 (`gemini-3.8-flash`)**:
   - Status: Failed (`503 UNAVAILABLE`)
   - Latency: 1128.41 ms
   - Error: `This model is currently experiencing high demand. Spikes in demand are usually temporary. Please try again later.`
4. **Attempt 4 (`gemini-3.5-flash-lite`)**:
   - Status: **Success** (`200 OK`)
   - Latency: 965.75 ms
   - Result: Successful extraction, full grounding, and deterministic correction.
