#!/usr/bin/env python3
"""Persist document chunks and pretrained embeddings in PostgreSQL/pgvector.

Step 21 implementation:
- Validates embedding model metadata, dimension (384), and chunk-vector alignment.
- Idempotently ensures schema and pgvector extension exist.
- Performs transactional, parameterized batch upsert on (corpus_id, chunk_id).
- Preserves full verbatim text, source document provenance, character offsets, and content hashes.
"""

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import numpy as np
except ImportError:
    np = None  # type: ignore

# Load local environment configuration (.env)
REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.extractors import load_dotenv

load_dotenv()

EXPECTED_DIMENSION = 384
DEFAULT_EMBEDDINGS_DIR = REPO_ROOT / "data" / "embeddings"
SCHEMA_SQL_PATH = REPO_ROOT / "scripts" / "init_db.sql"


def validate_artifacts(
    embeddings_dir: Path,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Any]:
    """Load and validate manifest, chunks, and embeddings before database operations.
    
    Raises:
        ImportError: If numpy is not installed.
        FileNotFoundError: If any required artifact is missing.
        ValueError: If model configuration, dimension, or chunk-vector alignment is invalid.
    """
    if np is None:
        raise ImportError(
            "numpy is required for embedding validation and ingestion. "
            "Install with: pip install -r requirements-embeddings.txt"
        )

    manifest_path = embeddings_dir / "manifest.json"
    chunks_path = embeddings_dir / "chunks.json"
    embeddings_path = embeddings_dir / "embeddings.npy"

    if not manifest_path.is_file():
        raise FileNotFoundError(f"Missing manifest file: {manifest_path}")
    if not chunks_path.is_file():
        raise FileNotFoundError(f"Missing chunks file: {chunks_path}")
    if not embeddings_path.is_file():
        raise FileNotFoundError(f"Missing embeddings file: {embeddings_path}")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    model_info = manifest.get("embedding_model", {})
    model_name = model_info.get("name")
    model_rev = model_info.get("revision")
    model_dim = model_info.get("dimension")

    if not model_name or not model_rev:
        raise ValueError(f"Manifest missing model name or revision: {model_info}")

    if model_dim != EXPECTED_DIMENSION:
        raise ValueError(
            f"Embedding dimension in manifest ({model_dim}) does not match expected {EXPECTED_DIMENSION}."
        )

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    embeddings = np.load(embeddings_path)

    # 1. Alignment verification
    if len(chunks) != embeddings.shape[0]:
        raise ValueError(
            f"Chunk count ({len(chunks)}) does not match embedding matrix rows ({embeddings.shape[0]})."
        )

    # 2. Dimension verification
    if embeddings.shape[1] != EXPECTED_DIMENSION:
        raise ValueError(
            f"Embedding matrix dimension ({embeddings.shape[1]}) does not match expected {EXPECTED_DIMENSION}."
        )

    # 3. Finite numbers check
    if not np.isfinite(embeddings).all():
        raise ValueError("Embedding matrix contains NaN or Inf values.")

    # 4. Normalization check
    norms = np.linalg.norm(embeddings, axis=1)
    if not np.allclose(norms, 1.0, atol=1e-3):
        raise ValueError(
            f"Embeddings are not unit normalized: min={norms.min():.4f}, max={norms.max():.4f}"
        )

    # 5. Chunk fields verification
    required_chunk_fields = {
        "chunk_id",
        "corpus_id",
        "text",
        "document_filename",
        "page_number",
        "start_char",
        "end_char",
        "token_count",
        "content_sha256",
        "component_id",
        "revision",
    }
    for idx, c in enumerate(chunks):
        missing = required_chunk_fields - set(c.keys())
        if missing:
            raise ValueError(f"Chunk at index {idx} ({c.get('chunk_id')}) missing fields: {missing}")
        if not c["text"] or not isinstance(c["text"], str):
            raise ValueError(f"Chunk at index {idx} has invalid or empty text.")

    return manifest, chunks, embeddings


def get_connection_config(
    host: Optional[str] = None,
    port: Optional[int] = None,
    dbname: Optional[str] = None,
    user: Optional[str] = None,
    password: Optional[str] = None,
) -> Dict[str, Any]:
    """Resolve database connection parameters from arguments or environment variables."""
    return {
        "host": host or os.environ.get("POSTGRES_HOST", "localhost"),
        "port": int(port or os.environ.get("POSTGRES_PORT", 5432)),
        "dbname": dbname or os.environ.get("POSTGRES_DB", "copilot_db"),
        "user": user or os.environ.get("POSTGRES_USER", "copilot_user"),
        "password": password or os.environ.get("POSTGRES_PASSWORD", "copilot_password"),
    }


def init_database_schema(conn) -> None:
    """Execute init_db.sql to ensure pgvector extension and document_chunks table exist."""
    if not SCHEMA_SQL_PATH.is_file():
        raise FileNotFoundError(f"Missing schema SQL file: {SCHEMA_SQL_PATH}")

    schema_sql = SCHEMA_SQL_PATH.read_text(encoding="utf-8")
    with conn.cursor() as cur:
        cur.execute(schema_sql)
    conn.commit()


def ingest_embeddings(
    embeddings_dir: Optional[Path] = None,
    connection_config: Optional[Dict[str, Any]] = None,
    batch_size: int = 100,
    ensure_schema: bool = True,
) -> Dict[str, Any]:
    """Ingest document chunks and embeddings into PostgreSQL/pgvector.
    
    Returns:
        Summary dict containing ingestion metrics and target database metadata.
    """
    try:
        import psycopg
        from pgvector.psycopg import register_vector
    except ImportError as e:
        raise ImportError(
            "psycopg and pgvector are required for database ingestion. "
            "Install with: pip install -r requirements-database.txt"
        ) from e

    dir_path = Path(embeddings_dir or DEFAULT_EMBEDDINGS_DIR)
    manifest, chunks, embeddings = validate_artifacts(dir_path)

    cfg = connection_config or get_connection_config()
    model_name = manifest["embedding_model"]["name"]
    model_revision = manifest["embedding_model"]["revision"]

    t0 = time.perf_counter()

    with psycopg.connect(
        host=cfg["host"],
        port=cfg["port"],
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
    ) as conn:
        if ensure_schema:
            init_database_schema(conn)

        register_vector(conn)

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

        total_chunks = len(chunks)
        with conn.transaction():
            with conn.cursor() as cur:
                for i in range(0, total_chunks, batch_size):
                    batch_chunks = chunks[i : i + batch_size]
                    batch_params = []
                    for j, c in enumerate(batch_chunks):
                        global_idx = i + j
                        vec = embeddings[global_idx]
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
                    cur.executemany(upsert_query, batch_params)

        # Confirm count in database
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM document_chunks;")
            total_db_rows = cur.fetchone()[0]

    elapsed = time.perf_counter() - t0

    return {
        "status": "success",
        "ingested_chunks": total_chunks,
        "total_database_rows": total_db_rows,
        "model_name": model_name,
        "model_revision": model_revision,
        "dimension": EXPECTED_DIMENSION,
        "elapsed_seconds": round(elapsed, 4),
        "target_database": {
            "host": cfg["host"],
            "port": cfg["port"],
            "dbname": cfg["dbname"],
            "user": cfg["user"],
            "table": "document_chunks",
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Ingest document chunks and pretrained embeddings into PostgreSQL/pgvector."
    )
    parser.add_argument(
        "--embeddings-dir",
        type=Path,
        default=DEFAULT_EMBEDDINGS_DIR,
        help=f"Directory containing chunks.json, embeddings.npy, manifest.json (default: {DEFAULT_EMBEDDINGS_DIR})",
    )
    parser.add_argument("--host", type=str, default=None, help="PostgreSQL host (default: POSTGRES_HOST or localhost)")
    parser.add_argument("--port", type=int, default=None, help="PostgreSQL port (default: POSTGRES_PORT or 5432)")
    parser.add_argument("--dbname", type=str, default=None, help="Database name (default: POSTGRES_DB or copilot_db)")
    parser.add_argument("--user", type=str, default=None, help="User name (default: POSTGRES_USER or copilot_user)")
    parser.add_argument("--password", type=str, default=None, help="Password (default: POSTGRES_PASSWORD or copilot_password)")
    parser.add_argument("--batch-size", type=int, default=100, help="Batch size for insertion (default: 100)")
    parser.add_argument(
        "--no-init-schema",
        action="store_true",
        help="Skip executing init_db.sql schema initialization before inserting",
    )

    args = parser.parse_args()

    cfg = get_connection_config(
        host=args.host,
        port=args.port,
        dbname=args.dbname,
        user=args.user,
        password=args.password,
    )

    print("=== Step 21 Document Embedding Ingestion ===")
    print(f"Embeddings Directory: {args.embeddings_dir}")
    print(f"Target Database:      {cfg['dbname']} at {cfg['host']}:{cfg['port']} (user: {cfg['user']})")

    try:
        result = ingest_embeddings(
            embeddings_dir=args.embeddings_dir,
            connection_config=cfg,
            batch_size=args.batch_size,
            ensure_schema=not args.no_init_schema,
        )
        print("\nIngestion Completed Successfully:")
        print(f"  Ingested Chunks:     {result['ingested_chunks']}")
        print(f"  Total Database Rows: {result['total_database_rows']}")
        print(f"  Model Identifier:    {result['model_name']}")
        print(f"  Model Revision:      {result['model_revision']}")
        print(f"  Vector Dimension:    {result['dimension']}")
        print(f"  Elapsed Time:        {result['elapsed_seconds']:.4f}s")
    except Exception as e:
        print(f"\n[ERROR] Ingestion failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
