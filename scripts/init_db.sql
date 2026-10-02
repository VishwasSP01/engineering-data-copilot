-- Repeatable database initialization and schema setup for Engineering Data Copilot (Step 21)
-- Enables pgvector and creates the document_chunks table preserving chunk metadata,
-- source provenance, verbatim text, model configuration, and 384-dimensional embeddings.

-- 1. Enable pgvector extension
CREATE EXTENSION IF NOT EXISTS vector;

-- 2. Document Chunks Table
CREATE TABLE IF NOT EXISTS document_chunks (
    id BIGSERIAL PRIMARY KEY,
    corpus_id VARCHAR(64) NOT NULL,
    chunk_id VARCHAR(128) NOT NULL,
    document_filename VARCHAR(255) NOT NULL,
    page_number INTEGER NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    token_count INTEGER NOT NULL,
    content_sha256 VARCHAR(64) NOT NULL,
    component_id VARCHAR(64) NOT NULL,
    revision VARCHAR(32) NOT NULL,
    document_id VARCHAR(64),
    text TEXT NOT NULL,
    model_name VARCHAR(128) NOT NULL,
    model_revision VARCHAR(64) NOT NULL,
    embedding vector(384) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uq_document_chunks_corpus_chunk UNIQUE (corpus_id, chunk_id)
);

-- 3. Composite metadata index for authoritative identity filtering
CREATE INDEX IF NOT EXISTS idx_document_chunks_identity 
ON document_chunks (corpus_id, component_id, revision);

-- 4. Document and page index for citation lookups
CREATE INDEX IF NOT EXISTS idx_document_chunks_document 
ON document_chunks (document_filename, page_number);

-- 5. HNSW cosine index for approximate nearest-neighbor search
CREATE INDEX IF NOT EXISTS idx_document_chunks_embedding_cosine 
ON document_chunks USING hnsw (embedding vector_cosine_ops);
