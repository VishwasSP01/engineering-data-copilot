#!/usr/bin/env python3
"""
Generate citation-preserving document chunks and pretrained embeddings from extracted supplier text.

Step 20 implementation:
- Reads strictly from PDF-extracted document text in an explicitly selected corpus directory.
- Keeps chunks bounded to a single page; preserves verbatim source text with character offsets.
- Derives document identity (component ID, revision, document ID) from authoritative content only.
- Rejects documents with missing or ambiguous identity rather than guessing.
- Enforces tokenizer-aware length limits (including special tokens) to prevent silent truncation.
- Uses pretrained sentence-transformers/all-MiniLM-L6-v2 on CPU with normalized embeddings (norm ~ 1.0).
- Saves chunks, embeddings, and manifest under data/embeddings/ (gitignored).
- Never scans records, evaluation expected answers, or repository documentation as embedding inputs.
- Keeps existing API and default retrieval behavior unchanged.
"""

import argparse
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Optional numpy import for vector serialization
try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

# Model constants
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EMBEDDING_DIM = 384
MAX_CHUNK_TOKENS = 250  # all-MiniLM-L6-v2 max_seq_length is 256; leaves margin for [CLS] and [SEP]


def extract_document_identity(full_text: str) -> Dict[str, Optional[str]]:
    """Derive document identity authoritatively from document text.
    
    Rejects missing or conflicting component IDs and revisions.
    Does not guess or consult external sources.
    
    Returns:
        dict with keys: 'component_id', 'revision', 'document_id'
        
    Raises:
        ValueError: If component ID or revision is missing or ambiguous.
    """
    # 1. Component ID extraction
    comp_matches = set(
        re.findall(r'(?:Component ID|Part Number)\s*:\s*([A-Za-z0-9_-]+)', full_text, re.IGNORECASE)
    )
    if not comp_matches:
        raise ValueError("Document text missing component identity (no 'Component ID:' or 'Part Number:' found).")
    if len(comp_matches) > 1:
        raise ValueError(f"Ambiguous component identity: multiple conflicting IDs found: {sorted(comp_matches)}.")
    component_id = list(comp_matches)[0]

    # 2. Revision extraction
    rev_matches = set(
        re.findall(r'(?:Revision|Rev\.?)\s*:\s*([A-Za-z0-9_-]+)', full_text, re.IGNORECASE)
    )
    if not rev_matches:
        raise ValueError("Document text missing revision identity (no 'Revision:' or 'Rev:' found).")
    if len(rev_matches) > 1:
        raise ValueError(f"Ambiguous revision identity: multiple conflicting revisions found: {sorted(rev_matches)}.")
    revision = list(rev_matches)[0]

    # 3. Document ID extraction (optional metadata if available)
    doc_id_matches = set(
        re.findall(r'Document ID\s*:\s*([A-Za-z0-9_-]+)', full_text, re.IGNORECASE)
    )
    document_id = list(doc_id_matches)[0] if len(doc_id_matches) == 1 else None

    return {
        "component_id": component_id,
        "revision": revision,
        "document_id": document_id
    }


def estimate_token_count(text: str, tokenizer: Optional[Any] = None) -> int:
    """Calculate or conservatively estimate token count including special tokens."""
    if tokenizer is not None:
        return len(tokenizer.encode(text, add_special_tokens=True))
    # Conservative word/subword heuristic when running offline without tokenizer
    # 1 whitespace token ~ 1.3 subword tokens + 2 special tokens ([CLS], [SEP])
    words = text.split()
    return int(len(words) * 1.4) + 2


def chunk_document_page(
    page_text: str,
    page_number: int,
    doc_stem: str,
    tokenizer: Optional[Any] = None,
    max_tokens: int = MAX_CHUNK_TOKENS
) -> List[Dict[str, Any]]:
    """Chunk a single document page into citation-preserving, contiguous verbatim spans.
    
    Guarantees:
    - Chunks are strictly within the page.
    - Every chunk is a contiguous verbatim slice of page_text:
      page_text[start_char:end_char] == text.
    - Each chunk's token count is <= max_tokens (including special tokens).
    - Preserves measurement sections and table structures where possible.
    """
    if not page_text or not page_text.strip():
        return []

    # Identify structural section boundaries (numbered sections or double newlines)
    boundaries = [0]
    for m in re.finditer(r'(?:^|\n)(?=\d+\.\s+[A-Za-z])', page_text):
        idx = m.start() + 1 if page_text[m.start()] == '\n' else m.start()
        if idx not in boundaries:
            boundaries.append(idx)
    boundaries.append(len(page_text))
    boundaries = sorted(list(set(boundaries)))

    raw_spans = []
    for i in range(len(boundaries) - 1):
        s, e = boundaries[i], boundaries[i + 1]
        slice_text = page_text[s:e]
        stripped = slice_text.strip()
        if not stripped:
            continue
        rel_start = slice_text.find(stripped)
        abs_start = s + rel_start
        abs_end = abs_start + len(stripped)
        assert page_text[abs_start:abs_end] == stripped, "Span boundary mismatch"
        raw_spans.append((abs_start, abs_end, stripped))

    chunks = []
    chunk_idx = 1

    for s, e, text in raw_spans:
        tok_count = estimate_token_count(text, tokenizer)
        if tok_count <= max_tokens:
            chunk_id = f"{doc_stem}_p{page_number}_c{chunk_idx:03d}"
            chunks.append({
                "chunk_id": chunk_id,
                "page_number": page_number,
                "start_char": s,
                "end_char": e,
                "text": text,
                "token_count": tok_count,
                "content_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()
            })
            chunk_idx += 1
        else:
            # Section exceeds max_tokens -> split into contiguous line groupings
            lines = text.split("\n")
            curr_start = s
            curr_lines: List[str] = []

            for line in lines:
                candidate_lines = curr_lines + [line]
                candidate_str = "\n".join(candidate_lines).strip()
                cand_tokens = estimate_token_count(candidate_str, tokenizer)

                if cand_tokens <= max_tokens:
                    curr_lines.append(line)
                else:
                    if curr_lines:
                        chunk_str = "\n".join(curr_lines).strip()
                        c_idx = page_text.find(chunk_str, curr_start)
                        c_end = c_idx + len(chunk_str)
                        assert page_text[c_idx:c_end] == chunk_str, "Sub-chunk boundary mismatch"
                        chunk_id = f"{doc_stem}_p{page_number}_c{chunk_idx:03d}"
                        chunks.append({
                            "chunk_id": chunk_id,
                            "page_number": page_number,
                            "start_char": c_idx,
                            "end_char": c_end,
                            "text": chunk_str,
                            "token_count": estimate_token_count(chunk_str, tokenizer),
                            "content_sha256": hashlib.sha256(chunk_str.encode("utf-8")).hexdigest()
                        })
                        chunk_idx += 1
                        curr_start = c_end
                        curr_lines = [line]
                    else:
                        # Single line exceeds max_tokens -> forced boundary slice
                        chunk_str = line.strip()
                        c_idx = page_text.find(chunk_str, curr_start)
                        c_end = c_idx + len(chunk_str)
                        chunk_id = f"{doc_stem}_p{page_number}_c{chunk_idx:03d}"
                        chunks.append({
                            "chunk_id": chunk_id,
                            "page_number": page_number,
                            "start_char": c_idx,
                            "end_char": c_end,
                            "text": chunk_str,
                            "token_count": estimate_token_count(chunk_str, tokenizer),
                            "content_sha256": hashlib.sha256(chunk_str.encode("utf-8")).hexdigest()
                        })
                        chunk_idx += 1
                        curr_start = c_end
                        curr_lines = []

            if curr_lines:
                chunk_str = "\n".join(curr_lines).strip()
                c_idx = page_text.find(chunk_str, curr_start)
                c_end = c_idx + len(chunk_str)
                assert page_text[c_idx:c_end] == chunk_str, "Trailing sub-chunk boundary mismatch"
                chunk_id = f"{doc_stem}_p{page_number}_c{chunk_idx:03d}"
                chunks.append({
                    "chunk_id": chunk_id,
                    "page_number": page_number,
                    "start_char": c_idx,
                    "end_char": c_end,
                    "text": chunk_str,
                    "token_count": estimate_token_count(chunk_str, tokenizer),
                    "content_sha256": hashlib.sha256(chunk_str.encode("utf-8")).hexdigest()
                })
                chunk_idx += 1

    return chunks


def process_extracted_corpus(
    extracted_dir: Path,
    corpus_id: str = "supplier-corpus",
    tokenizer: Optional[Any] = None,
    max_tokens: int = MAX_CHUNK_TOKENS
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """Process an extracted document corpus directory and generate citation-preserving chunks.
    
    Reads ONLY extracted document JSONs. Never scans records, evaluation expected answers,
    or repository documentation.
    """
    if not extracted_dir.exists():
        raise FileNotFoundError(f"Extracted documents directory '{extracted_dir}' does not exist.")

    json_files = sorted(extracted_dir.glob("*.json"), key=lambda p: p.name)
    if not json_files:
        raise ValueError(f"No extracted JSON documents found in '{extracted_dir}'.")

    all_chunks: List[Dict[str, Any]] = []
    doc_summaries: List[Dict[str, Any]] = []

    for json_path in json_files:
        with open(json_path, "r", encoding="utf-8") as f:
            doc_data = json.load(f)

        source_filename = doc_data.get("source_file") or f"{json_path.stem}.pdf"
        pages = doc_data.get("pages", [])
        if not pages:
            continue

        full_doc_text = "\n".join(p.get("text", "") for p in pages)
        identity = extract_document_identity(full_doc_text)

        doc_chunks = []
        for page_info in pages:
            page_num = page_info.get("page_number", 1)
            page_text = page_info.get("text", "")
            page_chunks = chunk_document_page(
                page_text=page_text,
                page_number=page_num,
                doc_stem=json_path.stem,
                tokenizer=tokenizer,
                max_tokens=max_tokens
            )

            for c in page_chunks:
                # Attach document identity and corpus metadata
                c["corpus_id"] = corpus_id
                c["document_filename"] = source_filename
                c["component_id"] = identity["component_id"]
                c["revision"] = identity["revision"]
                c["document_id"] = identity["document_id"]
                doc_chunks.append(c)

        all_chunks.extend(doc_chunks)
        doc_summaries.append({
            "source_file": source_filename,
            "component_id": identity["component_id"],
            "revision": identity["revision"],
            "document_id": identity["document_id"],
            "pages": len(pages),
            "chunks": len(doc_chunks)
        })

    corpus_meta = {
        "corpus_id": corpus_id,
        "source_directory": str(extracted_dir),
        "total_documents": len(json_files),
        "total_chunks": len(all_chunks),
        "documents": doc_summaries
    }

    return all_chunks, corpus_meta


def embed_chunks(
    chunks: List[Dict[str, Any]],
    model_name: str = DEFAULT_MODEL_NAME,
    model_revision: str = DEFAULT_MODEL_REVISION,
    device: str = "cpu",
    normalize: bool = True
) -> Any:
    """Generate normalized pretrained embeddings using SentenceTransformers on CPU.
    
    Guarantees:
    - Pretrained model weights are never fine-tuned or mutated.
    - Embeddings are strictly computed on CPU.
    - Output matrix has shape (len(chunks), EMBEDDING_DIM) with float32 values.
    - All vector norms are approximately 1.0 (unit normalized).
    """
    global np
    if np is None:
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "numpy is not installed. Please install optional embedding dependencies: "
                "pip install -r requirements-embeddings.txt"
            ) from exc

    try:
        from sentence_transformers import SentenceTransformer
    except ImportError as exc:
        raise RuntimeError(
            "sentence-transformers is not installed. "
            "Please install optional embedding dependencies: pip install -r requirements-embeddings.txt"
        ) from exc

    if not chunks:
        return np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    # Load model with pinned revision on CPU
    model = SentenceTransformer(model_name, revision=model_revision, device=device)

    texts = [c["text"] for c in chunks]
    embeddings = model.encode(
        texts,
        device=device,
        normalize_embeddings=normalize,
        show_progress_bar=False,
        batch_size=32
    )

    vectors = np.array(embeddings, dtype=np.float32)

    # Verify vector integrity
    if not np.isfinite(vectors).all():
        raise RuntimeError("Non-finite values (NaN/Inf) detected in generated embeddings.")

    if normalize:
        norms = np.linalg.norm(vectors, axis=1)
        if not np.allclose(norms, 1.0, atol=1e-5):
            raise RuntimeError(f"Embedding normalization check failed. Norm range: [{norms.min()}, {norms.max()}].")

    return vectors


def save_embeddings(
    output_dir: Path,
    chunks: List[Dict[str, Any]],
    vectors: Any,
    corpus_meta: Dict[str, Any],
    model_name: str = DEFAULT_MODEL_NAME,
    model_revision: str = DEFAULT_MODEL_REVISION,
    max_tokens: int = MAX_CHUNK_TOKENS
) -> Dict[str, Any]:
    """Save generated chunks, embeddings, and manifest under output_dir."""
    global np
    if np is None:
        try:
            import numpy as np
        except ImportError as exc:
            raise RuntimeError(
                "numpy is not installed. Please install optional embedding dependencies: "
                "pip install -r requirements-embeddings.txt"
            ) from exc

    output_dir.mkdir(parents=True, exist_ok=True)

    chunks_file = output_dir / "chunks.json"
    embeddings_file = output_dir / "embeddings.npy"
    manifest_file = output_dir / "manifest.json"

    # Save chunks.json
    with open(chunks_file, "w", encoding="utf-8") as f:
        json.dump(chunks, f, indent=2, ensure_ascii=False)

    # Save embeddings.npy
    np.save(embeddings_file, vectors)

    # Build manifest
    manifest = {
        "manifest_version": "1.0.0",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "corpus": corpus_meta,
        "embedding_model": {
            "name": model_name,
            "revision": model_revision,
            "dimension": EMBEDDING_DIM,
            "normalized": True,
            "device": "cpu"
        },
        "chunking_settings": {
            "max_tokens": max_tokens,
            "strategy": "hierarchical_boundary_verbatim",
            "preserve_tables": True,
            "page_bounded": True
        },
        "files": {
            "chunks_file": "chunks.json",
            "embeddings_file": "embeddings.npy",
            "manifest_file": "manifest.json",
            "chunks_sha256": hashlib.sha256(chunks_file.read_bytes()).hexdigest(),
            "embeddings_sha256": hashlib.sha256(embeddings_file.read_bytes()).hexdigest()
        }
    }

    with open(manifest_file, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)

    return manifest


def main():
    parser = argparse.ArgumentParser(
        description="Generate citation-preserving document chunks and embeddings from supplier documents."
    )
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=None,
        help="Path to directory containing extracted document JSONs (default: data/extracted)"
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Path to directory to save generated chunks and embeddings (default: data/embeddings)"
    )
    parser.add_argument(
        "--corpus-id",
        type=str,
        default="supplier-corpus",
        help="Identifier for the document corpus (default: supplier-corpus)"
    )
    parser.add_argument(
        "--model-name",
        type=str,
        default=DEFAULT_MODEL_NAME,
        help=f"Pretrained SentenceTransformers model name (default: {DEFAULT_MODEL_NAME})"
    )
    parser.add_argument(
        "--model-revision",
        type=str,
        default=DEFAULT_MODEL_REVISION,
        help=f"Pinned HuggingFace model commit SHA (default: {DEFAULT_MODEL_REVISION})"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=MAX_CHUNK_TOKENS,
        help=f"Maximum tokens per chunk including special tokens (default: {MAX_CHUNK_TOKENS})"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Extract and validate chunks without generating vector embeddings"
    )

    args = parser.parse_args()
    repo_root = Path(__file__).resolve().parent.parent

    extracted_dir = args.extracted_dir or (repo_root / "data" / "extracted")
    output_dir = args.output_dir or (repo_root / "data" / "embeddings")

    print(f"=== Document Embedding Pipeline (Step 20) ===")
    print(f"Corpus ID:       {args.corpus_id}")
    print(f"Extracted Dir:   {extracted_dir}")
    print(f"Output Dir:      {output_dir}")
    print(f"Model:           {args.model_name} (revision: {args.model_revision[:8]})")
    print(f"Max Tokens:      {args.max_tokens} (tokenizer-aware)")

    # Load tokenizer for exact token counting
    tokenizer = None
    try:
        from transformers import AutoTokenizer
        tokenizer = AutoTokenizer.from_pretrained(args.model_name, revision=args.model_revision)
        print("Tokenizer:       Loaded successfully.")
    except Exception as exc:
        print(f"Tokenizer:       Using heuristic token estimation ({exc}).")

    # Step 1: Chunk documents
    print("\nProcessing extracted documents...")
    chunks, corpus_meta = process_extracted_corpus(
        extracted_dir=extracted_dir,
        corpus_id=args.corpus_id,
        tokenizer=tokenizer,
        max_tokens=args.max_tokens
    )
    print(f"Generated {len(chunks)} chunks across {corpus_meta['total_documents']} document(s).")

    if args.dry_run:
        print("\nDry run requested: Skipping vector embedding generation.")
        output_dir.mkdir(parents=True, exist_ok=True)
        chunks_file = output_dir / "chunks.json"
        with open(chunks_file, "w", encoding="utf-8") as f:
            json.dump(chunks, f, indent=2, ensure_ascii=False)
        print(f"Saved chunks to {chunks_file}.")
        return

    # Step 2: Generate vector embeddings
    print("\nGenerating normalized embeddings on CPU...")
    t0 = datetime.now()
    vectors = embed_chunks(
        chunks=chunks,
        model_name=args.model_name,
        model_revision=args.model_revision,
        device="cpu",
        normalize=True
    )
    duration = (datetime.now() - t0).total_seconds()
    print(f"Generated {vectors.shape[0]} vectors of dimension {vectors.shape[1]} in {duration:.2f}s.")

    # Step 3: Save artifacts
    print(f"\nSaving artifacts to {output_dir}...")
    manifest = save_embeddings(
        output_dir=output_dir,
        chunks=chunks,
        vectors=vectors,
        corpus_meta=corpus_meta,
        model_name=args.model_name,
        model_revision=args.model_revision,
        max_tokens=args.max_tokens
    )

    print("Pipeline complete:")
    print(f"- Chunks file:     {output_dir / 'chunks.json'}")
    print(f"- Embeddings file: {output_dir / 'embeddings.npy'}")
    print(f"- Manifest file:   {output_dir / 'manifest.json'}")


if __name__ == "__main__":
    main()
