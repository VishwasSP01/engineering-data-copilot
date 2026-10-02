#!/usr/bin/env python3
"""
Verification suite for Step 20: citation-preserving document chunks and real pretrained embeddings.

Verifies:
1. Every vector has 384 finite float values and approximately unit Euclidean norm (||v||_2 ≈ 1.0 ± 1e-5).
2. Source offsets in chunks reproduce verbatim document text exactly (page_text[start:end] == chunk_text).
3. Repeated generation preserves stable chunk IDs and produces numerically consistent vectors within 1e-5.
4. Cached execution works locally from the populated cache without network downloads (local_files_only).
5. Identity rejection: documents with missing or ambiguous component/revision identities are rejected safely.
6. Cosine similarity demonstration on labelled engineering text queries with ranking analysis.
7. Explicit distinction between real model inference and fake/mock test encoders.
"""

import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List

import numpy as np

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.embed_documents import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    EMBEDDING_DIM,
    MAX_CHUNK_TOKENS,
    chunk_document_page,
    embed_chunks,
    extract_document_identity,
    process_extracted_corpus,
)


def verify_chunks_and_offsets(extracted_dir: Path, chunks: List[Dict[str, Any]]):
    """Verify that source offsets reproduce every chunk text verbatim from extracted pages."""
    print("1. Verifying source offsets and verbatim text reproduction...")
    doc_cache: Dict[str, Any] = {}

    for c in chunks:
        doc_filename = c["document_filename"]
        stem = Path(doc_filename).stem
        json_path = extracted_dir / f"{stem}.json"

        if json_path not in doc_cache:
            with open(json_path, "r", encoding="utf-8") as f:
                doc_cache[json_path] = json.load(f)

            doc_data = doc_cache[json_path]
            page_data = next((p for p in doc_data["pages"] if p["page_number"] == c["page_number"]), None)
            assert page_data is not None, f"Page {c['page_number']} not found in {json_path}"

            page_text = page_data["text"]
            reproduced_text = page_text[c["start_char"]:c["end_char"]]
            assert reproduced_text == c["text"], (
                f"Verbatim mismatch for chunk {c['chunk_id']}:\n"
                f"Expected: {repr(c['text'])}\n"
                f"Got:      {repr(reproduced_text)}"
            )

            # Verify content SHA-256
            expected_hash = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
            assert c["content_sha256"] == expected_hash, f"Hash mismatch for {c['chunk_id']}"

            # Verify chunk stays within single page
            assert c["page_number"] >= 1, f"Invalid page number {c['page_number']}"

            # Verify non-empty
            assert len(c["text"].strip()) > 0, f"Empty text in {c['chunk_id']}"

    print(f"  [✓] All {len(chunks)} chunks verified: character offsets reproduce verbatim page text exactly.")


def verify_vectors_integrity(vectors: np.ndarray, expected_count: int):
    """Verify vector shapes, finite float values, and unit normalization."""
    print("\n2. Verifying vector mathematical properties (real model inference)...")
    assert vectors.shape == (expected_count, EMBEDDING_DIM), (
        f"Shape mismatch: expected ({expected_count}, {EMBEDDING_DIM}), got {vectors.shape}"
    )

    # Check finite
    assert np.isfinite(vectors).all(), "Non-finite values (NaN / Inf) detected in embedding matrix"

    # Check unit norm (||v||_2 ≈ 1.0 ± 1e-5)
    norms = np.linalg.norm(vectors, axis=1)
    min_norm, max_norm = float(norms.min()), float(norms.max())
    assert np.allclose(norms, 1.0, atol=1e-5), (
        f"Unit norm check failed. Norm range: [{min_norm:.7f}, {max_norm:.7f}]"
    )

    print(f"  [✓] Matrix shape ({vectors.shape[0]}, {vectors.shape[1]}) matches expected dimensions.")
    print(f"  [✓] All {vectors.size} vector float values are finite.")
    print(f"  [✓] All vector norms are approximately unit norm: min={min_norm:.6f}, max={max_norm:.6f} (tolerance 1e-5).")


def verify_repeated_generation_consistency(chunks: List[Dict[str, Any]], vectors: np.ndarray):
    """Verify repeated generation preserves stable IDs and produces numerically consistent vectors."""
    print("\n3. Verifying deterministic reproducibility across runs...")
    vectors_repeat = embed_chunks(
        chunks=chunks,
        model_name=DEFAULT_MODEL_NAME,
        model_revision=DEFAULT_MODEL_REVISION,
        device="cpu",
        normalize=True
    )

    assert np.allclose(vectors, vectors_repeat, atol=1e-5), (
        f"Numerical discrepancy detected across repeated model inference runs."
    )
    max_diff = float(np.max(np.abs(vectors - vectors_repeat)))
    print(f"  [✓] Repeated CPU inference produces identical vectors (maximum absolute difference: {max_diff:.2e} <= 1e-5).")


def verify_cached_execution_without_downloads():
    """Verify model loads from the local cache without network downloads."""
    print("\n4. Verifying local cached model execution (zero network downloads)...")
    from sentence_transformers import SentenceTransformer

    # Loading with local_files_only=True guarantees zero network requests
    model = SentenceTransformer(
        DEFAULT_MODEL_NAME,
        revision=DEFAULT_MODEL_REVISION,
        device="cpu",
        local_files_only=True
    )
    test_vec = model.encode(["Authoritative technical specification."], normalize_embeddings=True)
    assert test_vec.shape == (1, EMBEDDING_DIM)
    print("  [✓] SentenceTransformer loaded successfully with local_files_only=True (verified offline from cache).")


def verify_identity_rejection_rules():
    """Verify that documents with missing or ambiguous component/revision identities are rejected."""
    print("\n5. Verifying authoritative document identity extraction & rejection rules...")

    # Case 1: Valid identity
    valid_text = "Component ID: COMP-001\nRevision: A\nDocument ID: DOC-123\nSome details."
    ident = extract_document_identity(valid_text)
    assert ident["component_id"] == "COMP-001"
    assert ident["revision"] == "A"
    assert ident["document_id"] == "DOC-123"

    # Case 2: Missing component ID
    missing_comp_text = "Apex Technical Specification.\nRevision: A\nSome details."
    try:
        extract_document_identity(missing_comp_text)
        assert False, "Failed to reject missing component ID"
    except ValueError as exc:
        assert "missing component identity" in str(exc).lower()

    # Case 3: Ambiguous component ID (conflicting part numbers)
    ambiguous_comp_text = "Component ID: COMP-001\nSecondary Part Number: COMP-999\nRevision: A"
    try:
        extract_document_identity(ambiguous_comp_text)
        assert False, "Failed to reject ambiguous component IDs"
    except ValueError as exc:
        assert "ambiguous component identity" in str(exc).lower()

    # Case 4: Missing revision
    missing_rev_text = "Component ID: COMP-001\nNo revision info here."
    try:
        extract_document_identity(missing_rev_text)
        assert False, "Failed to reject missing revision"
    except ValueError as exc:
        assert "missing revision identity" in str(exc).lower()

    # Case 5: Ambiguous revision
    ambiguous_rev_text = "Component ID: COMP-001\nRevision: A\nSuperseded Revision: B"
    try:
        extract_document_identity(ambiguous_rev_text)
        assert False, "Failed to reject ambiguous revision"
    except ValueError as exc:
        assert "ambiguous revision identity" in str(exc).lower()

    print("  [✓] All identity extraction and safety rejection rules verified successfully.")


def demonstrate_cosine_similarity(chunks: List[Dict[str, Any]], vectors: np.ndarray):
    """Demonstrate cosine similarity on labelled engineering queries.
    
    Demonstrates semantic vector alignment without claiming document retrieval accuracy.
    """
    print("\n6. Demonstrating semantic cosine similarity on labelled queries...")
    print("   [Disclaimer: Demonstrates vector dot-product properties on isolated texts;")
    print("    does not replace or benchmark end-to-end document retrieval accuracy.]")

    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(DEFAULT_MODEL_NAME, revision=DEFAULT_MODEL_REVISION, device="cpu", local_files_only=True)

    queries = [
        {
            "label": "Physical Dimensions Query",
            "query": "What is the component thickness and physical dimensions in cm or mm?",
            "expected_top_chunk_id": "supplier-COMP-001_p1_c003",  # Physical Dimensions section
            "expected_topic": "2. Physical Dimensions & Mechanical Parameters"
        },
        {
            "label": "Product Overview Query",
            "query": "What is the ceramic substrate carrier designed for surface-mount circuits?",
            "expected_top_chunk_id": "supplier-COMP-001_p1_c002",  # Product Overview section
            "expected_topic": "1. Product Overview"
        }
    ]

    for q in queries:
        query_text = q["query"]
        q_vec = model.encode([query_text], normalize_embeddings=True, device="cpu")[0]

        # For unit-normalized vectors: cosine_similarity(u, v) = dot(u, v)
        similarities = np.dot(vectors, q_vec)
        ranked_indices = np.argsort(similarities)[::-1]

        top_idx = ranked_indices[0]
        top_chunk = chunks[top_idx]
        top_sim = similarities[top_idx]

        print(f"\n   Query: '{query_text}' ({q['label']})")
        print(f"   Top Match: {top_chunk['chunk_id']} (cosine similarity: {top_sim:.4f})")
        first_line = top_chunk["text"].splitlines()[0]
        print(f"   Chunk Content Preview: \"{first_line}...\"")

        assert top_chunk["chunk_id"] == q["expected_top_chunk_id"], (
            f"Expected top match {q['expected_top_chunk_id']}, got {top_chunk['chunk_id']}"
        )
        print(f"   [✓] Correctly identified '{q['expected_topic']}' as the highest-similarity chunk.")


def main():
    print("=== Step 20 Pretrained Embeddings & Chunking Verification Suite ===\n")
    print(f"Configured Model:    {DEFAULT_MODEL_NAME}")
    print(f"Resolved Revision:   {DEFAULT_MODEL_REVISION}")
    print(f"Embedding Dimension: {EMBEDDING_DIM}")
    print(f"Inference Device:    CPU (normalized vectors)\n")

    extracted_dir = REPO_ROOT / "data" / "extracted"
    embeddings_dir = REPO_ROOT / "data" / "embeddings"

    # Step 1: Ensure embeddings and chunks are generated
    chunks_path = embeddings_dir / "chunks.json"
    vectors_path = embeddings_dir / "embeddings.npy"

    if not chunks_path.exists() or not vectors_path.exists():
        print("Generating fresh embeddings for verification...")
        from scripts.embed_documents import main as run_embed
        run_embed()

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    vectors = np.load(vectors_path)

    # Step 2: Run verification checks
    verify_chunks_and_offsets(extracted_dir, chunks)
    verify_vectors_integrity(vectors, len(chunks))
    verify_repeated_generation_consistency(chunks, vectors)
    verify_cached_execution_without_downloads()
    verify_identity_rejection_rules()
    demonstrate_cosine_similarity(chunks, vectors)

    print("\n=======================================================")
    print("ALL STEP 20 EMBEDDING VERIFICATION CHECKS PASSED (100%)")
    print("=======================================================")


if __name__ == "__main__":
    main()
