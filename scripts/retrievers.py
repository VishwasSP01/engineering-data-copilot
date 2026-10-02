#!/usr/bin/env python3
"""Pluggable evidence retrieval interfaces and implementations for Engineering Data Copilot.

Step 22 implementation:
- Adds explicit retriever selection: 'baseline' (default) or 'pgvector'.
- BaselineRetriever: deterministic document matching & section extraction from data/extracted/.
- PgVectorRetriever: metadata-filtered vector retrieval in PostgreSQL/pgvector.
  * Encodes queries using pinned sentence-transformers/all-MiniLM-L6-v2 on CPU.
  * Strict metadata filtering on corpus_id, component_id, revision, model_name, model_revision.
  * Preserves conflict detection across the full eligible context before top-k selection.
  * Exact cosine ranking with deterministic tie-breaking (page_number, start_char, chunk_id).
  * Returns citation-preserving contiguous verbatim spans and page provenance.
  * Detects missing configuration, database failures, and model incompatibilities without silent fallback.
"""

import abc
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.extractors import load_dotenv

load_dotenv()

# Constants
DEFAULT_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_MODEL_REVISION = "1110a243fdf4706b3f48f1d95db1a4f5529b4d41"
EXPECTED_DIMENSION = 384
DEFAULT_CORPUS_ID = "supplier-corpus"


class BaseRetriever(abc.ABC):
    """Abstract base class for evidence retrievers."""

    @property
    @abc.abstractmethod
    def name(self) -> str:
        """Retriever implementation name."""
        pass

    @abc.abstractmethod
    def retrieve(
        self,
        record: Dict[str, Any],
        extracted_dir: Optional[Path] = None,
        corpus_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Retrieve evidence for an engineering record.
        
        Returns:
            Structured dictionary containing status, document_filename, page_number,
            evidence_passage, context_type, and reason.
        """
        pass


class BaselineRetriever(BaseRetriever):
    """Deterministic document-matching baseline retriever."""

    @property
    def name(self) -> str:
        return "baseline"

    def retrieve(
        self,
        record: Dict[str, Any],
        extracted_dir: Optional[Path] = None,
        corpus_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        from scripts.retrieve_evidence import retrieve_evidence_baseline

        t0 = time.perf_counter()
        res = retrieve_evidence_baseline(record, extracted_dir=extracted_dir)
        duration_ms = (time.perf_counter() - t0) * 1000.0

        res["retriever"] = {
            "name": self.name,
            "mode": "deterministic_text",
            "duration_ms": round(duration_ms, 3),
            "status": "success",
            "error_type": None,
        }
        return res


class PgVectorRetriever(BaseRetriever):
    """PostgreSQL/pgvector metadata-filtered semantic retriever."""

    def __init__(
        self,
        connection_config: Optional[Dict[str, Any]] = None,
        model_name: str = DEFAULT_MODEL_NAME,
        model_revision: str = DEFAULT_MODEL_REVISION,
        embedding_model_instance: Optional[Any] = None,
        db_connection_factory: Optional[Any] = None,
    ):
        self._connection_config = connection_config
        self.model_name = model_name
        self.model_revision = model_revision
        self._model_instance = embedding_model_instance
        self._db_connection_factory = db_connection_factory

    @property
    def name(self) -> str:
        return "pgvector"

    def _get_connection_config(self) -> Dict[str, Any]:
        if self._connection_config:
            return self._connection_config
        return {
            "host": os.environ.get("POSTGRES_HOST", "localhost"),
            "port": int(os.environ.get("POSTGRES_PORT", 5432)),
            "dbname": os.environ.get("POSTGRES_DB", "copilot_db"),
            "user": os.environ.get("POSTGRES_USER", "copilot_user"),
            "password": os.environ.get("POSTGRES_PASSWORD", "copilot_password"),
        }

    def _get_model(self):
        if self._model_instance is not None:
            return self._model_instance
        try:
            from sentence_transformers import SentenceTransformer

            self._model_instance = SentenceTransformer(
                self.model_name,
                device="cpu",
                local_files_only=True,
            )
            return self._model_instance
        except Exception as e:
            raise RuntimeError(
                f"Failed to load embedding model '{self.model_name}': {e}. "
                "Ensure requirements-embeddings.txt is installed and weights are cached."
            ) from e

    def build_query_text(self, component_id: str, attribute_name: str) -> str:
        """Construct semantic search query from record identity and requested attribute.
        
        Never includes expected answers or target values.
        """
        clean_comp = component_id.strip()
        clean_attr = attribute_name.strip()
        return f"Component {clean_comp} {clean_attr} physical dimension parameter specification"

    def retrieve(
        self,
        record: Dict[str, Any],
        extracted_dir: Optional[Path] = None,
        corpus_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        active_corpus = corpus_id or DEFAULT_CORPUS_ID

        record_id = record.get("record_id") or record.get("case_id") or "UNKNOWN-RECORD"
        component_id = record.get("component_id") or record.get("part_number")
        revision = record.get("revision")
        attribute_name = record.get("attribute_name") or record.get("attribute") or record.get("measurement")

        base_response = {
            "record_id": record_id,
            "component_id": component_id,
            "revision": revision,
            "attribute_name": attribute_name,
        }

        # 1. Basic record validation
        if not component_id:
            return {
                **base_response,
                "status": "insufficient_evidence",
                "retrieval_status": "insufficient_evidence",
                "document_filename": None,
                "page_number": None,
                "evidence_passage": None,
                "context_type": None,
                "evidence": None,
                "retriever": {
                    "name": self.name,
                    "mode": "vector_filtered",
                    "duration_ms": 0.0,
                    "status": "success",
                    "error_type": None,
                },
                "reason": "Record does not specify a valid component_id or part_number.",
            }

        if not attribute_name:
            return {
                **base_response,
                "status": "insufficient_evidence",
                "retrieval_status": "insufficient_evidence",
                "document_filename": None,
                "page_number": None,
                "evidence_passage": None,
                "context_type": None,
                "evidence": None,
                "retriever": {
                    "name": self.name,
                    "mode": "vector_filtered",
                    "duration_ms": 0.0,
                    "status": "success",
                    "error_type": None,
                },
                "reason": "Record does not specify an attribute_name to investigate.",
            }

        # 2. Check dependencies
        try:
            import psycopg
            from pgvector.psycopg import register_vector
        except ImportError as e:
            return {
                **base_response,
                "status": "error",
                "retrieval_status": "error",
                "document_filename": None,
                "page_number": None,
                "evidence_passage": None,
                "context_type": None,
                "evidence": None,
                "retriever": {
                    "name": self.name,
                    "mode": "vector_filtered",
                    "duration_ms": 0.0,
                    "status": "error",
                    "error_type": "CONFIGURATION_ERROR",
                    "error_message": "psycopg or pgvector driver not installed. Install requirements-database.txt.",
                },
                "reason": "Database vector retrieval dependencies are not installed.",
            }

        # 3. Generate query embedding
        try:
            model = self._get_model()
            query_text = self.build_query_text(component_id, attribute_name)
            query_vector = model.encode(
                query_text,
                convert_to_numpy=True,
                normalize_embeddings=True,
            )
            if query_vector.shape != (EXPECTED_DIMENSION,):
                raise ValueError(
                    f"Generated query vector dimension {query_vector.shape} != expected ({EXPECTED_DIMENSION},)"
                )
        except Exception as e:
            sanitized_err = re.sub(r'(/[^/]+)+', '<path>', str(e))
            return {
                **base_response,
                "status": "error",
                "retrieval_status": "error",
                "document_filename": None,
                "page_number": None,
                "evidence_passage": None,
                "context_type": None,
                "evidence": None,
                "retriever": {
                    "name": self.name,
                    "mode": "vector_filtered",
                    "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                    "status": "error",
                    "error_type": "MODEL_INCOMPATIBLE",
                    "error_message": f"Embedding model error: {sanitized_err}",
                },
                "reason": f"Failed to encode retrieval query: {sanitized_err}",
            }

        # 4. Connect to database and execute query
        cfg = self._get_connection_config()
        try:
            if self._db_connection_factory is not None:
                conn_cm = self._db_connection_factory()
            else:
                conn_cm = psycopg.connect(
                    host=cfg["host"],
                    port=cfg["port"],
                    dbname=cfg["dbname"],
                    user=cfg["user"],
                    password=cfg["password"],
                    connect_timeout=3,
                )

            with conn_cm as conn:
                try:
                    register_vector(conn)
                except Exception:
                    pass
                with conn.cursor() as cur:
                    # Check if table exists
                    cur.execute(
                        "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'document_chunks');"
                    )
                    if not cur.fetchone()[0]:
                        return {
                            **base_response,
                            "status": "error",
                            "retrieval_status": "error",
                            "document_filename": None,
                            "page_number": None,
                            "evidence_passage": None,
                            "context_type": None,
                            "evidence": None,
                            "retriever": {
                                "name": self.name,
                                "mode": "vector_filtered",
                                "duration_ms": round((time.perf_counter() - t0) * 1000.0, 3),
                                "status": "error",
                                "error_type": "DATABASE_ERROR",
                                "error_message": "Table 'document_chunks' does not exist in database.",
                            },
                            "reason": "Database schema is uninitialized (missing table 'document_chunks').",
                        }

                    # Fetch ALL eligible chunks for this (corpus_id, component_id, revision)
                    # before ranking, to preserve conflict detection across the full source context.
                    # Explicitly use a MATERIALIZED CTE to guarantee exact filtered search over the
                    # metadata-filtered subset (via B-Tree index) and prevent the query planner from
                    # attempting an approximate HNSW index scan when ordering by cosine distance.
                    cur.execute(
                        """
                        WITH filtered_chunks AS MATERIALIZED (
                            SELECT chunk_id, document_filename, page_number,
                                   start_char, end_char, token_count, content_sha256,
                                   component_id, revision, document_id, text,
                                   embedding
                            FROM document_chunks
                            WHERE corpus_id = %s
                              AND component_id = %s
                              AND revision = %s
                              AND model_name = %s
                              AND model_revision = %s
                        )
                        SELECT chunk_id, document_filename, page_number,
                               start_char, end_char, token_count, content_sha256,
                               component_id, revision, document_id, text,
                               (embedding <=> %s) AS cosine_distance
                        FROM filtered_chunks
                        ORDER BY (embedding <=> %s) ASC, page_number ASC, start_char ASC, chunk_id ASC;
                        """,
                        (
                            active_corpus,
                            component_id,
                            revision,
                            self.model_name,
                            self.model_revision,
                            query_vector,
                            query_vector,
                        ),
                    )
                    eligible_rows = cur.fetchall()

                    # If no eligible rows found, check whether component exists at all or revision mismatched
                    if not eligible_rows:
                        cur.execute(
                            "SELECT COUNT(*) FROM document_chunks WHERE corpus_id = %s AND component_id = %s;",
                            (active_corpus, component_id),
                        )
                        comp_count = cur.fetchone()[0]
                        elapsed_ms = (time.perf_counter() - t0) * 1000.0

                        if comp_count == 0:
                            reason = f"Component ID '{component_id}' not found in extracted document content."
                        else:
                            reason = f"Document content matches component '{component_id}' but revision '{revision}' was not confirmed."

                        return {
                            **base_response,
                            "status": "insufficient_evidence",
                            "retrieval_status": "insufficient_evidence",
                            "document_filename": None,
                            "page_number": None,
                            "evidence_passage": None,
                            "context_type": None,
                            "evidence": None,
                            "retriever": {
                                "name": self.name,
                                "mode": "vector_filtered",
                                "corpus_id": active_corpus,
                                "duration_ms": round(elapsed_ms, 3),
                                "status": "success",
                                "error_type": None,
                            },
                            "reason": reason,
                        }

                    # 5. Conflict Detection across the full eligible source context
                    # Requirement 4: A conflicting measurement must not disappear merely because its chunk ranked lower.
                    from scripts.retrieve_evidence import parse_direct_specification_line

                    direct_specs = []
                    chunks_with_attribute = []

                    for row in eligible_rows:
                        cid, filename, p_num, s_char, e_char, t_cnt, c_hash, c_id, rev, doc_id, text, dist = row
                        # Check lines in chunk for direct specifications
                        for line in text.splitlines():
                            parsed = parse_direct_specification_line(line, attribute_name)
                            if parsed:
                                direct_specs.append({
                                    "val": parsed[0],
                                    "unit": parsed[1],
                                    "line": line.strip(),
                                    "chunk_id": cid,
                                    "filename": filename,
                                    "page_number": p_num,
                                    "chunk_text": text,
                                    "distance": dist,
                                })

                        if re.search(rf'\b{re.escape(attribute_name)}\b', text, re.IGNORECASE):
                            chunks_with_attribute.append(row)

                    if direct_specs:
                        distinct_measurements = {(c["val"], c["unit"]) for c in direct_specs}
                        if len(distinct_measurements) > 1:
                            conflicts_str = ", ".join(f"{val} {unit}" for val, unit in sorted(distinct_measurements))
                            elapsed_ms = (time.perf_counter() - t0) * 1000.0
                            return {
                                **base_response,
                                "status": "ambiguous_evidence",
                                "retrieval_status": "ambiguous_evidence",
                                "document_filename": None,
                                "page_number": None,
                                "evidence_passage": None,
                                "context_type": None,
                                "evidence": None,
                                "retriever": {
                                    "name": self.name,
                                    "mode": "vector_filtered",
                                    "corpus_id": active_corpus,
                                    "duration_ms": round(elapsed_ms, 3),
                                    "status": "success",
                                    "error_type": None,
                                },
                                "reason": f"Conflicting measurement values found for '{attribute_name}': {conflicts_str}.",
                            }

                    # If no chunk contains attribute_name or direct specification
                    if not chunks_with_attribute and not direct_specs:
                        elapsed_ms = (time.perf_counter() - t0) * 1000.0
                        return {
                            **base_response,
                            "status": "insufficient_evidence",
                            "retrieval_status": "insufficient_evidence",
                            "document_filename": None,
                            "page_number": None,
                            "evidence_passage": None,
                            "context_type": None,
                            "evidence": None,
                            "retriever": {
                                "name": self.name,
                                "mode": "vector_filtered",
                                "corpus_id": active_corpus,
                                "duration_ms": round(elapsed_ms, 3),
                                "status": "success",
                                "error_type": None,
                            },
                            "reason": f"No measurement evidence found for attribute '{attribute_name}' in matching document(s).",
                        }

                    # 6. Rank eligible chunks and select top candidate
                    # Filter candidates to those containing evidence or specifications
                    if direct_specs:
                        # Direct specification line present: prioritize the chunk containing it
                        # sorted by cosine distance
                        direct_specs.sort(key=lambda x: (x["distance"], x["page_number"]))
                        top_candidate = direct_specs[0]
                        selected_text = top_candidate["chunk_text"]
                        selected_filename = top_candidate["filename"]
                        selected_page = top_candidate["page_number"]
                        selected_sim = 1.0 - float(top_candidate["distance"])
                        context_type = "chunk"
                    else:
                        # Chunks with attribute: already sorted by cosine distance ASC in SQL
                        top_row = chunks_with_attribute[0]
                        cid, filename, p_num, s_char, e_char, t_cnt, c_hash, c_id, rev, doc_id, text, dist = top_row
                        selected_text = text
                        selected_filename = filename
                        selected_page = p_num
                        selected_sim = 1.0 - float(dist)
                        context_type = "chunk"

        except Exception as e:
            # Catch database connection, query, and operational failures
            elapsed_ms = (time.perf_counter() - t0) * 1000.0
            sanitized_err = re.sub(r'password=\S+', 'password=***', str(e), flags=re.IGNORECASE)
            sanitized_err = re.sub(r'(/[^/]+)+', '<path>', sanitized_err)
            return {
                **base_response,
                "status": "error",
                "retrieval_status": "error",
                "document_filename": None,
                "page_number": None,
                "evidence_passage": None,
                "context_type": None,
                "evidence": None,
                "retriever": {
                    "name": self.name,
                    "mode": "vector_filtered",
                    "duration_ms": round(elapsed_ms, 3),
                    "status": "error",
                    "error_type": "DATABASE_ERROR",
                    "error_message": f"Database operation failed: {sanitized_err}",
                },
                "reason": f"PostgreSQL vector retrieval failed: {sanitized_err}",
            }

        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        evidence_dict = {
            "document_filename": selected_filename,
            "page_number": selected_page,
            "supporting_passage": selected_text,
            "context_type": context_type,
            "similarity_score": round(selected_sim, 4),
        }

        return {
            **base_response,
            "status": "evidence_found",
            "retrieval_status": "evidence_found",
            "document_filename": selected_filename,
            "page_number": selected_page,
            "evidence_passage": selected_text,
            "context_type": context_type,
            "evidence": evidence_dict,
            "retriever": {
                "name": self.name,
                "mode": "vector_filtered",
                "corpus_id": active_corpus,
                "similarity_score": round(selected_sim, 4),
                "duration_ms": round(elapsed_ms, 3),
                "status": "success",
                "error_type": None,
            },
            "reason": (
                f"Found relevant {context_type} containing '{attribute_name}' via pgvector "
                f"(cosine similarity: {selected_sim:.4f}) on page {selected_page} of {selected_filename}."
            ),
        }


def get_retriever(name: str = "baseline", **kwargs) -> BaseRetriever:
    """Factory function resolving requested retriever instance."""
    clean_name = (name or "baseline").strip().lower()
    if clean_name in ("baseline", "deterministic", "regex"):
        return BaselineRetriever()
    elif clean_name in ("pgvector", "vector", "postgres"):
        return PgVectorRetriever(**kwargs)
    raise ValueError(f"Unknown retriever '{name}'. Supported retrievers: 'baseline', 'pgvector'.")
