# Step 22: Retriever Comparative Evaluation Report

> **Scope & Purpose**: Compare deterministic document-matching evidence retrieval (`baseline`) against PostgreSQL/pgvector metadata-filtered semantic chunk retrieval (`pgvector`). Both runs hold the deterministic regex/tuple parser fixed (zero Gemini API calls) across all 16 cases (10 baseline + 6 challenge).

## Executive Summary

- **Suite Evaluated**: `ALL` (16 cases total)
- **Extractor Provider**: Deterministic regex and tuple parser (held fixed; zero model calls)
- **Baseline Retriever Pass Rate**: **15/16 (93.8%)**
- **PgVector Retriever Pass Rate**: **15/16 (93.8%)**
- **Concordance Between Retrievers**: **16/16 (100.0%)**
- **Evidence Retrieval Accuracy (Both)**: **8/8 (100.0%)** (gold cases)
- **Retrieval Abstention Accuracy (Both)**: **6/6 (100.0%)** (safety boundaries)

## Information Retrieval (IR) Benchmark on Gold Evidence Cases

- **Gold Evidence Cases**: **9 cases** (cases expecting evidence citation)
- **Relevance Definition**: A candidate chunk is relevant iff it originates from the authoritative supplier document and expected page, and contains the ground-truth supporting passage verbatim (allowing whitespace normalization).
- **Recall@1 (Rank 1 Hit Rate)**: **9/9 (100.0%)**
- **Recall@2 (Top 2 Hit Rate)**: **9/9 (100.0%)**
- **Recall@3 (Top 3 Hit Rate)**: **9/9 (100.0%)**
- **Mean Reciprocal Rank (MRR)**: **1.0**

| Metric | Baseline Retriever | PgVector Retriever | Target Denominator | Notes |
|---|---|---|---|---|
| **Recall@1** | 9/9 (100.0%) | **9/9 (100.0%)** | 9 gold cases | Relevant chunk ranked #1 |
| **Recall@2** | 9/9 (100.0%) | **9/9 (100.0%)** | 9 gold cases | Relevant chunk in top 2 |
| **Recall@3** | 9/9 (100.0%) | **9/9 (100.0%)** | 9 gold cases | Relevant chunk in top 3 |
| **MRR** | 1.000 | **1.0** | 9 gold cases | Average reciprocal rank |

## Per-Case Comparative Results

| Case ID | Category | Expected Outcome | Baseline | PgVector | Cos Sim | IR Rank | Agreement | Base Lat (ms) | PgVec Lat (ms) |
|---|---|---|---|---|---|---|---|---|---|
| `case-01-correction-cm-to-mm` | correction | `correction_proposed` | `correction_proposed` | `correction_proposed` | 0.8259 | Rank 1 | ✓ Match | 1.30 | 3181.25 |
| `case-02-correction-mm-to-cm` | correction | `correction_proposed` | `correction_proposed` | `correction_proposed` | 0.7498 | Rank 1 | ✓ Match | 2.80 | 64.43 |
| `case-03-agreement-mm` | abstention | `no_change` | `no_change` | `no_change` | 0.7997 | Rank 1 | ✓ Match | 0.87 | 53.43 |
| `case-04-agreement-cm` | abstention | `no_change` | `no_change` | `no_change` | 0.7504 | Rank 1 | ✓ Match | 0.96 | 45.79 |
| `case-05-unknown-component` | abstention | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ Match | 0.67 | 44.41 |
| `case-06-incorrect-revision` | abstention | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ Match | 0.69 | 50.51 |
| `case-07-missing-measurement` | abstention | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ Match | 0.90 | 50.33 |
| `case-08-conflicting-evidence` | abstention | `ambiguous_evidence` | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ Match | 0.55 | 40.56 |
| `case-09-unsupported-unit` | abstention | `needs_review` | `needs_review` | `needs_review` | 0.7835 | Rank 1 | ✓ Match | 0.56 | 40.30 |
| `case-10-malformed-measurement` | abstention | `needs_review` | `needs_review` | `needs_review` | — | — | ✓ Match | 0.14 | 0.07 |
| `challenge-01-complete-sentence` | challenge_sentence | `correction_proposed` | `needs_review` | `needs_review` | 0.8041 | Rank 1 | ✓ Match | 0.71 | 41.78 |
| `challenge-02-table-value-unit-columns` | challenge_table | `correction_proposed` | `correction_proposed` | `correction_proposed` | 0.8292 | Rank 1 | ✓ Match | 0.70 | 42.54 |
| `challenge-03-split-lines-label-measurement` | challenge_split_lines | `correction_proposed` | `correction_proposed` | `correction_proposed` | 0.7663 | Rank 1 | ✓ Match | 2.33 | 39.30 |
| `challenge-04-distracting-measurements` | challenge_distracting | `no_change` | `no_change` | `no_change` | 0.7554 | Rank 1 | ✓ Match | 0.83 | 42.18 |
| `challenge-05-incorrect-revision` | challenge_revision | `insufficient_evidence` | `insufficient_evidence` | `insufficient_evidence` | — | — | ✓ Match | 0.65 | 40.27 |
| `challenge-06-conflicting-statements` | challenge_conflict | `ambiguous_evidence` | `ambiguous_evidence` | `ambiguous_evidence` | — | — | ✓ Match | 0.59 | 103.91 |

## Latency Profile Comparison

| Retriever | Median Latency (ms) | Mean Latency (ms) | Min Latency (ms) | Max Latency (ms) | Notes |
|---|---|---|---|---|---|
| **Baseline** | 0.71 | 0.95 | 0.14 | 2.8 | Pure in-memory regex scanning over extracted document text |
| **PgVector** | 43.48 | 242.57 | 0.07 | 3181.25 | Sentence-Transformers CPU query encoding + PostgreSQL cosine similarity query |

## Comparative Findings & Safety Analysis

1. **Complete Concordance (16/16 Cases, 100.0%)**: PgVector retrieval achieved 100% decision and citation concordance with the baseline across all 16 cases. Both retrievers pass 10/10 baseline cases and 5/6 challenge cases (with `challenge-01` failing at measurement extraction due to documented regex phrasing limitations).
2. **Exact Cosine Ranking Accuracy (Recall@1 = 100%)**: Across all 9 gold evidence cases, the relevant chunk containing the specification was ranked at position #1 with cosine similarity ranging from 0.7498 to 0.8292. Zero distracting or irrelevant chunks outranked authoritative specifications.
3. **Conflict Detection Preserved Before Top-K Truncation**: In both `case-08-conflicting-evidence` and `challenge-06-conflicting-statements`, PgVectorRetriever inspected all eligible candidate chunks matching the component and revision before ranking. Because competing values were identified, retrieval immediately returned `ambiguous_evidence`, preventing false positives.
4. **Strict Identity & Revision Filtering**: For `case-05` (unknown component), `case-06` (incorrect revision), `case-07` (missing measurement), and `challenge-05` (incorrect revision), SQL filters on `(corpus_id, component_id, revision)` strictly prevented retrieval from returning chunks belonging to other components or revisions.
5. **Deterministic Arithmetic Unaltered**: In all cases where corrections were proposed, Python `Decimal` arithmetic performed exact unit conversion (e.g. 0.8 cm -> 8.0 mm), ensuring zero floating-point imprecision.

## Limitations Notice
- All 16 cases are synthetic technical datasheets with consistent structure.
- Database retrieval was tested with exact cosine distance on CPU embeddings; performance on multi-gigabyte corpora will benefit from the existing HNSW index.

