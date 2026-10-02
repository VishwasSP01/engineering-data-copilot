"""Offline unit tests for citation-preserving document chunking and identity extraction."""

import hashlib
import json
import unittest
from pathlib import Path

from scripts.embed_documents import (
    chunk_document_page,
    extract_document_identity,
    process_extracted_corpus,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTED_DIR = REPO_ROOT / "data" / "extracted"


class TestCitationPreservingChunking(unittest.TestCase):
    """Test suite verifying verbatim boundary preservation and identity extraction."""

    def test_extract_valid_identity(self):
        """Authoritative component ID, revision, and document ID are extracted cleanly."""
        text = (
            "Apex Microelectronics Corp. — Supplier Datasheet\n"
            "Component ID: COMP-001\n"
            "Revision: A\n"
            "Document ID: DOC-SUP-COMP-001\n"
            "Effective Date: 2026-10-01\n"
        )
        ident = extract_document_identity(text)
        self.assertEqual(ident["component_id"], "COMP-001")
        self.assertEqual(ident["revision"], "A")
        self.assertEqual(ident["document_id"], "DOC-SUP-COMP-001")

    def test_reject_missing_component_identity(self):
        """Documents missing component identity raise ValueError rather than guessing."""
        text = "Apex Datasheet\nRevision: A\nSome specifications."
        with self.assertRaises(ValueError) as ctx:
            extract_document_identity(text)
        self.assertIn("missing component identity", str(ctx.exception).lower())

    def test_reject_ambiguous_component_identity(self):
        """Documents containing conflicting component IDs raise ValueError."""
        text = (
            "Component ID: COMP-001\n"
            "Secondary Part Number: COMP-999\n"
            "Revision: A\n"
        )
        with self.assertRaises(ValueError) as ctx:
            extract_document_identity(text)
        self.assertIn("ambiguous component identity", str(ctx.exception).lower())

    def test_reject_missing_revision_identity(self):
        """Documents missing revision identity raise ValueError."""
        text = "Component ID: COMP-001\nNo revision info here."
        with self.assertRaises(ValueError) as ctx:
            extract_document_identity(text)
        self.assertIn("missing revision identity", str(ctx.exception).lower())

    def test_reject_ambiguous_revision_identity(self):
        """Documents containing multiple conflicting revisions raise ValueError."""
        text = (
            "Component ID: COMP-001\n"
            "Revision: A\n"
            "Superseded Revision: B\n"
        )
        with self.assertRaises(ValueError) as ctx:
            extract_document_identity(text)
        self.assertIn("ambiguous revision identity", str(ctx.exception).lower())

    def test_chunking_exact_verbatim_reproduction(self):
        """Every generated chunk's character offsets reproduce page_text[start:end] exactly."""
        sample_page = (
            "SYNTHETIC HEADER\nComponent ID: COMP-001\nRevision: A\n\n"
            "1. Product Overview\nThe COMP-001 is a ceramic carrier.\n\n"
            "2. Physical Dimensions & Mechanical Parameters\n"
            "Component thickness: 0.8 cm.\n"
            "Parameter\nNominal Value\nLength 25.0 mm\nWidth 15.0 mm\n\n"
            "3. Synthetic Notice\nTesting only.\n"
        )

        chunks = chunk_document_page(
            page_text=sample_page,
            page_number=1,
            doc_stem="supplier-test",
            max_tokens=100
        )

        self.assertGreaterEqual(len(chunks), 3)

        for c in chunks:
            # 1. Exact verbatim reproduction
            reproduced = sample_page[c["start_char"]:c["end_char"]]
            self.assertEqual(reproduced, c["text"])

            # 2. Content SHA-256 match
            expected_hash = hashlib.sha256(c["text"].encode("utf-8")).hexdigest()
            self.assertEqual(c["content_sha256"], expected_hash)

            # 3. Page number integrity
            self.assertEqual(c["page_number"], 1)

            # 4. Non-empty
            self.assertGreater(len(c["text"]), 0)

    def test_process_extracted_corpus_offline(self):
        """Corpus processing produces valid chunks across all extracted documents in data/extracted."""
        if not EXTRACTED_DIR.exists():
            self.skipTest(f"Directory {EXTRACTED_DIR} does not exist.")

        chunks, meta = process_extracted_corpus(
            extracted_dir=EXTRACTED_DIR,
            corpus_id="test-corpus",
            max_tokens=250
        )

        self.assertGreater(len(chunks), 0)
        self.assertGreater(meta["total_documents"], 0)

        for c in chunks:
            self.assertEqual(c["corpus_id"], "test-corpus")
            self.assertIsNotNone(c["component_id"])
            self.assertIsNotNone(c["revision"])
            self.assertTrue(c["chunk_id"].startswith("supplier-"))


if __name__ == "__main__":
    unittest.main()
