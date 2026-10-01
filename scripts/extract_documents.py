#!/usr/bin/env python3
"""
Extract text from PDF documents in data/documents/ while preserving page citation info.

Saves structured extraction outputs to data/extracted/<doc_stem>.json.
Follows Step 4 requirements:
- Reads PDFs strictly from data/documents/.
- Extracts text per page, preserving source filename and 1-indexed page numbers.
- Processes files in a deterministic, sorted order.
- Reports unreadable PDFs or empty/non-extractable pages without silently ignoring failures.
- Never accesses or includes data from evaluation/expected/.
"""

import argparse
import json
import sys
from pathlib import Path
from pypdf import PdfReader
from pypdf.errors import PdfReadError


def extract_pdf(pdf_path: Path) -> dict:
    """Extract text from a single PDF document page by page.
    
    Raises:
        RuntimeError: If the PDF cannot be read or if any page has no extractable text.
    """
    source_filename = pdf_path.name
    print(f"Processing '{source_filename}'...")

    try:
        reader = PdfReader(str(pdf_path))
    except (PdfReadError, Exception) as exc:
        raise RuntimeError(f"Unreadable PDF '{source_filename}': {exc}") from exc

    if len(reader.pages) == 0:
        raise RuntimeError(f"PDF '{source_filename}' has 0 pages.")

    pages_data = []
    empty_pages = []

    for idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text()
        except Exception as exc:
            raise RuntimeError(f"Failed extracting text from page {idx} in '{source_filename}': {exc}") from exc

        if not page_text or not page_text.strip():
            empty_pages.append(idx)
        else:
            pages_data.append({
                "page_number": idx,
                "text": page_text
            })

    if empty_pages:
        raise RuntimeError(
            f"Extraction failed for '{source_filename}': Page(s) {empty_pages} have no extractable text. "
            "Scanned or empty pages are not silently accepted."
        )

    return {
        "source_file": source_filename,
        "pages": pages_data
    }


def main():
    parser = argparse.ArgumentParser(description="Extract text from PDFs in data/documents/ with citation preservation.")
    parser.add_argument(
        "--docs-dir",
        type=Path,
        default=None,
        help="Directory containing PDF documents (defaults to repository data/documents)."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save extracted JSON files (defaults to repository data/extracted)."
    )
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    docs_dir = args.docs_dir or (repo_root / "data" / "documents")
    output_dir = args.output_dir or (repo_root / "data" / "extracted")

    if not docs_dir.exists():
        print(f"Error: Documents directory '{docs_dir}' does not exist.", file=sys.stderr)
        sys.exit(1)

    pdf_files = sorted(docs_dir.glob("*.pdf"), key=lambda p: p.name)
    if not pdf_files:
        print(f"Error: No PDF files found in '{docs_dir}'.", file=sys.stderr)
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    extracted_count = 0
    errors = []

    for pdf_path in pdf_files:
        try:
            doc_data = extract_pdf(pdf_path)
            output_file = output_dir / f"{pdf_path.stem}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(doc_data, f, indent=2, ensure_ascii=False)
            print(f"Saved: {output_file} ({len(doc_data['pages'])} page(s))")
            extracted_count += 1
        except Exception as exc:
            errors.append((pdf_path.name, str(exc)))
            print(f"ERROR: {exc}", file=sys.stderr)

    print("\nExtraction Summary:")
    print(f"- Total PDFs found: {len(pdf_files)}")
    print(f"- Successfully extracted: {extracted_count}")
    print(f"- Failed: {len(errors)}")

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
