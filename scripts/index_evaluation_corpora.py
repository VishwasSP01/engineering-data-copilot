#!/usr/bin/env python3
"""Index evaluation suite corpora into PostgreSQL/pgvector under isolated corpus IDs.

Step 22 implementation:
- Processes extracted documents across all 10 baseline cases and 6 challenge cases.
- Uses isolated corpus IDs: 'eval-<case_dir_name>'.
- Generates normalized embeddings with pinned model sentence-transformers/all-MiniLM-L6-v2.
- Performs transactional, idempotent upserts into document_chunks.
- Indexes ONLY authoritative document text, never expected answers or records.
"""

import argparse
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.embed_documents import (
    DEFAULT_MODEL_NAME,
    DEFAULT_MODEL_REVISION,
    embed_chunks,
    process_extracted_corpus,
)
from scripts.extractors import load_dotenv
from scripts.ingest_embeddings import get_connection_config

load_dotenv()


def index_corpus_directory(
    extracted_dir: Path,
    corpus_id: str,
    conn: Any,
    model_instance: Optional[Any] = None,
    model_name: str = DEFAULT_MODEL_NAME,
    model_revision: str = DEFAULT_MODEL_REVISION,
) -> int:
    """Extract chunks, embed them, and upsert into document_chunks for a single corpus."""
    try:
        chunks, meta = process_extracted_corpus(extracted_dir, corpus_id=corpus_id)
    except Exception as e:
        print(f"  [WARN] Skipping {corpus_id} ({extracted_dir}): {e}")
        return 0

    if not chunks:
        return 0

    if model_instance is not None:
        texts = [c["text"] for c in chunks]
        embeddings = model_instance.encode(texts, normalize_embeddings=True)
    else:
        embeddings = embed_chunks(
            chunks,
            model_name=model_name,
            model_revision=model_revision,
            device="cpu",
            normalize=True,
        )

    upsert_query = """
        INSERT INTO document_chunks (
            corpus_id, chunk_id, document_filename, page_number,
            start_char, end_char, token_count, content_sha256,
            component_id, revision, document_id, text,
            model_name, model_revision, embedding
        ) VALUES (
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s, %s,
            %s, %s, %s
        )
        ON CONFLICT (corpus_id, chunk_id) DO UPDATE SET
            document_filename = EXCLUDED.document_filename,
            page_number = EXCLUDED.page_number,
            start_char = EXCLUDED.start_char,
            end_char = EXCLUDED.end_char,
            token_count = EXCLUDED.token_count,
            content_sha256 = EXCLUDED.content_sha256,
            component_id = EXCLUDED.component_id,
            revision = EXCLUDED.revision,
            document_id = EXCLUDED.document_id,
            text = EXCLUDED.text,
            model_name = EXCLUDED.model_name,
            model_revision = EXCLUDED.model_revision,
            embedding = EXCLUDED.embedding;
    """

    batch_params = []
    for idx, c in enumerate(chunks):
        vec = embeddings[idx]
        batch_params.append(
            (
                c["corpus_id"],
                c["chunk_id"],
                c["document_filename"],
                c["page_number"],
                c["start_char"],
                c["end_char"],
                c["token_count"],
                c["content_sha256"],
                c["component_id"],
                c["revision"],
                c.get("document_id"),
                c["text"],
                model_name,
                model_revision,
                vec,
            )
        )

    with conn.transaction():
        with conn.cursor() as cur:
            cur.executemany(upsert_query, batch_params)

    return len(chunks)


def index_all_evaluation_corpora(
    cases_dir: Optional[Path] = None,
    connection_config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Index all baseline and challenge evaluation case documents into PostgreSQL/pgvector."""
    try:
        import psycopg
        from pgvector.psycopg import register_vector
        from sentence_transformers import SentenceTransformer
    except ImportError as e:
        raise RuntimeError(
            f"Missing required dependencies for indexing: {e}. "
            "Install requirements-database.txt and requirements-embeddings.txt."
        ) from e

    base_cases = Path(cases_dir or (REPO_ROOT / "evaluation" / "cases"))
    cfg = connection_config or get_connection_config()

    print("=== Indexing Evaluation Corpora in PostgreSQL/pgvector ===")
    print(f"Cases Directory: {base_cases}")
    print(f"Target Database: {cfg['dbname']} at {cfg['host']}:{cfg['port']}")

    t0 = time.perf_counter()

    # Preload SentenceTransformer model once on CPU
    print(f"Loading embedding model '{DEFAULT_MODEL_NAME}' on CPU...")
    model = SentenceTransformer(
        DEFAULT_MODEL_NAME,
        revision=DEFAULT_MODEL_REVISION,
        device="cpu",
        local_files_only=True,
    )

    case_dirs = sorted([d for d in base_cases.iterdir() if d.is_dir()])
    total_indexed_chunks = 0
    indexed_corpora = []

    with psycopg.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
    ) as conn:
        register_vector(conn)

        for case_dir in case_dirs:
            ext_dir = case_dir / "extracted"
            if not ext_dir.exists():
                continue

            corpus_id = f"eval-{case_dir.name}"
            count = index_corpus_directory(
                extracted_dir=ext_dir,
                corpus_id=corpus_id,
                conn=conn,
                model_instance=model,
            )
            print(f"  [✓] {case_dir.name}: {count} chunks indexed under corpus '{corpus_id}'")
            total_indexed_chunks += count
            indexed_corpora.append({"case": case_dir.name, "corpus_id": corpus_id, "chunks": count})

        # Also confirm default supplier-corpus from data/extracted
        default_ext = REPO_ROOT / "data" / "extracted"
        if default_ext.exists():
            def_count = index_corpus_directory(
                extracted_dir=default_ext,
                corpus_id="supplier-corpus",
                conn=conn,
                model_instance=model,
            )
            print(f"  [✓] data/extracted: {def_count} chunks indexed under corpus 'supplier-corpus'")
            total_indexed_chunks += def_count
            indexed_corpora.append({"case": "supplier-corpus", "corpus_id": "supplier-corpus", "chunks": def_count})

        # Total rows in table
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks;")
            total_db_rows = cur.fetchone()[0]

    elapsed = time.perf_counter() - t0
    print(f"\nIndexing complete in {elapsed:.2f}s:")
    print(f"  Total Corpora Indexed: {len(indexed_corpora)}")
    print(f"  Total Chunks Ingested: {total_indexed_chunks}")
    print(f"  Total Database Rows:   {total_db_rows}")

    return {
        "status": "success",
        "total_corpora": len(indexed_corpora),
        "total_chunks_indexed": total_indexed_chunks,
        "total_db_rows": total_db_rows,
        "elapsed_seconds": round(elapsed, 3),
        "corpora": indexed_corpora,
    }


def main():
    parser = argparse.ArgumentParser(description="Index evaluation corpora into PostgreSQL/pgvector.")
    parser.add_argument(
        "--cases-dir",
        type=Path,
        default=None,
        help="Path to evaluation cases directory (default: evaluation/cases)",
    )
    args = parser.parse_args()

    try:
        index_all_evaluation_corpora(cases_dir=args.cases_dir)
    except Exception as e:
        print(f"Error during indexing: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
