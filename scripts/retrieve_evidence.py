#!/usr/bin/env python3
"""
Evidence retrieval for Engineering Data Investigation Copilot.

Step 12 implementation:
- Reads a supplied engineering record JSON and extracted documents in data/extracted/ only.
- Identifies component ID, revision, and attribute name from record.
- Matches component ID and revision explicitly in document content (strict word boundaries, no partial ID matches).
- Decouples finding relevant evidence from parsing a complete measurement.
- Preserves precise-passage retrieval when an unambiguous direct specification line exists.
- Provides fallback for eligible documents containing the requested measurement label:
  * Returns a contiguous verbatim section containing the label, value, unit, and table headers.
  * If a reliable section boundary cannot be determined, returns the eligible page's verbatim text.
  * Explicitly identifies whether the context is a 'passage', 'section', or 'page'.
- Preserves filename and 1-based page provenance.
- Never rewrites text, never joins disconnected excerpts into a fabricated quote, and never discards competing measurements.
- Resolves conflicts: returns 'ambiguous_evidence' if conflicting measurements exist for the attribute.
- Returns 'insufficient_evidence' if no matching component, revision, or measurement evidence is found.
- Generic to any requested measurement; never reads evaluation/expected/ or project documentation.
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


def match_component_id(text: str, component_id: str) -> bool:
    """Explicitly match component ID in text with strict boundaries.
    
    Prevents partial ID matches (e.g. COMP-001 matching COMP-0010 or COMP-001-B).
    """
    pattern = rf'(?<![A-Za-z0-9_-]){re.escape(component_id)}(?![A-Za-z0-9_-])'
    return bool(re.search(pattern, text, re.IGNORECASE))


def match_revision(text: str, revision: Optional[str]) -> bool:
    """Explicitly match revision in text with technical revision prefixes.
    
    Matches forms like 'Revision: A', 'Rev A', 'Rev. A', 'revision A'.
    Prevents matching arbitrary standalone single letters in prose.
    """
    if not revision:
        return True
    clean_rev = revision.strip()
    if clean_rev.lower().startswith("rev"):
        clean_rev = re.sub(r'^rev(?:ision)?\.?\s*', '', clean_rev, flags=re.IGNORECASE).strip()

    pattern = rf'\b(?:rev(?:ision)?\.?)\s*:?\s*{re.escape(clean_rev)}(?![A-Za-z0-9_-])'
    return bool(re.search(pattern, text, re.IGNORECASE))


def parse_direct_specification_line(line: str, attribute_name: str) -> Optional[Tuple[float, str]]:
    """Check if a line is a direct, standalone specification statement for attribute_name.
    
    Returns (value, unit) if matched, None otherwise.
    Matches lines such as:
    - 'Component thickness: 0.8 cm.'
    - 'thickness: 0.8 cm'
    - 'thickness = 0.8 cm'
    - 'Overall component thickness: 0.8 cm ± 0.02 cm.'
    Does not match compound lines (e.g. dimensions lists) or incomplete lines.
    """
    clean_line = line.strip()
    pattern = (
        rf'^(?:[A-Za-z0-9_-]+\s+)*{re.escape(attribute_name)}\s*(?:[:=]|\bis\b)\s*'
        rf'(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)(?:\s*[±+/-]\s*\d+(?:\.\d+)?\s*[a-zA-Zµ°Ω%]+)?[.;]?$'
    )
    m = re.match(pattern, clean_line, re.IGNORECASE)
    if m:
        return float(m.group(1)), m.group(2).lower()
    return None


def is_direct_specification_line(line: str, attribute_name: str) -> bool:
    """Check if a line is a direct specification statement for the attribute (legacy helper)."""
    return parse_direct_specification_line(line, attribute_name) is not None


def extract_section_or_page(page_text: str, attribute_name: str) -> Tuple[str, str]:
    """Extract a contiguous verbatim section containing attribute_name, or fall back to full page.
    
    Returns (context_text, context_type) where context_type is 'section' or 'page'.
    """
    # Pattern for section boundaries in technical datasheets:
    # Numbered headings (e.g. '1. Product Overview', '2. Physical Dimensions & Mechanical Parameters')
    heading_pattern = r'(?:^|\n)(?=\d+\.\s+[A-Za-z])'
    matches = list(re.finditer(heading_pattern, page_text))
    
    if matches:
        boundaries = []
        for m in matches:
            b = m.start() + 1 if page_text[m.start()] == '\n' else m.start()
            boundaries.append(b)
        
        if boundaries[0] > 0:
            boundaries.insert(0, 0)
        boundaries.append(len(page_text))
        
        candidate_sections = []
        for i in range(len(boundaries) - 1):
            start = boundaries[i]
            end = boundaries[i + 1]
            chunk = page_text[start:end].strip()
            if chunk and re.search(rf'\b{re.escape(attribute_name)}\b', chunk, re.IGNORECASE):
                # Preserve exact verbatim slice from page_text
                idx = page_text.find(chunk, start)
                if idx != -1:
                    verbatim_slice = page_text[idx:idx + len(chunk)]
                else:
                    verbatim_slice = chunk
                candidate_sections.append(verbatim_slice)
        
        if candidate_sections:
            # Prioritize dimensional / parameter specification sections over metadata/notice sections
            for sec in candidate_sections:
                first_line = sec.splitlines()[0].lower()
                if any(kw in first_line for kw in ("dimension", "parameter", "specification", "mechanical", "physical")):
                    return sec, "section"
            return candidate_sections[0], "section"
    
    # If no reliable section boundary can be determined, return full page verbatim text
    page_stripped = page_text.strip()
    idx = page_text.find(page_stripped)
    verbatim_page = page_text[idx:idx + len(page_stripped)] if idx != -1 else page_text
    return verbatim_page, "page"


def retrieve_evidence(record_path: Path, extracted_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Retrieve evidence for an engineering record from extracted documents."""
    repo_root = Path(__file__).resolve().parent.parent
    if extracted_dir is None:
        extracted_dir = repo_root / "data" / "extracted"

    if not record_path.exists():
        raise FileNotFoundError(f"Record file not found: {record_path}")

    with open(record_path, "r", encoding="utf-8") as f:
        record = json.load(f)

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
            "reason": "Record does not specify a valid component_id or part_number."
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
            "reason": "Record does not specify an attribute_name to investigate."
        }

    if not extracted_dir.exists():
        return {
            **base_response,
            "status": "insufficient_evidence",
            "retrieval_status": "insufficient_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "context_type": None,
            "evidence": None,
            "reason": f"Extracted documents directory '{extracted_dir}' does not exist."
        }

    # Locate candidate documents in data/extracted/
    doc_ref = record.get("document_reference")
    ref_filename = None
    if isinstance(doc_ref, dict):
        ref_filename = doc_ref.get("filename")
    elif isinstance(doc_ref, str):
        ref_filename = doc_ref

    all_json_files = sorted(extracted_dir.glob("*.json"), key=lambda p: p.name)
    candidate_files = []
    if ref_filename:
        stem = Path(ref_filename).stem
        for p in all_json_files:
            if p.stem == stem or p.name == f"{ref_filename}.json":
                candidate_files.append(p)
    if not candidate_files:
        candidate_files = all_json_files

    if not candidate_files:
        return {
            **base_response,
            "status": "insufficient_evidence",
            "retrieval_status": "insufficient_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "context_type": None,
            "evidence": None,
            "reason": f"No extracted JSON documents found in '{extracted_dir}'."
        }

    matching_docs = []
    component_found_anywhere = False

    for json_file in candidate_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)
        except Exception:
            continue

        pages = doc_data.get("pages", [])
        full_text = "\n".join(p.get("text", "") for p in pages)

        # Requirement 4: Match component ID and revision explicitly in document content
        has_comp = match_component_id(full_text, component_id)
        if has_comp:
            component_found_anywhere = True
            has_rev = match_revision(full_text, revision)
            if has_rev:
                matching_docs.append(doc_data)

    if not component_found_anywhere:
        return {
            **base_response,
            "status": "insufficient_evidence",
            "retrieval_status": "insufficient_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "context_type": None,
            "evidence": None,
            "reason": f"Component ID '{component_id}' not found in extracted document content."
        }

    if not matching_docs:
        return {
            **base_response,
            "status": "insufficient_evidence",
            "retrieval_status": "insufficient_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "context_type": None,
            "evidence": None,
            "reason": f"Document content matches component '{component_id}' but revision '{revision}' was not confirmed."
        }

    # Requirement 3 & 4: Preserve precise-passage retrieval when unambiguous direct specification line exists
    direct_specs = []
    for doc in matching_docs:
        source_file = doc.get("source_file", "unknown.pdf")
        for page in sorted(doc.get("pages", []), key=lambda p: p.get("page_number", 1)):
            p_num = page.get("page_number", 1)
            p_text = page.get("text", "")
            for line in p_text.splitlines():
                parsed = parse_direct_specification_line(line, attribute_name)
                if parsed:
                    clean_line = line.strip()
                    # Ensure line exists verbatim in page_text
                    passage_str = clean_line if clean_line in p_text else line
                    direct_specs.append({
                        "val": parsed[0],
                        "unit": parsed[1],
                        "passage": passage_str,
                        "source_file": source_file,
                        "page_number": p_num,
                        "page_text": p_text
                    })

    if direct_specs:
        distinct_measurements = {(c["val"], c["unit"]) for c in direct_specs}
        if len(distinct_measurements) > 1:
            conflicts_str = ", ".join(f"{val} {unit}" for val, unit in sorted(distinct_measurements))
            return {
                **base_response,
                "status": "ambiguous_evidence",
                "retrieval_status": "ambiguous_evidence",
                "document_filename": None,
                "page_number": None,
                "evidence_passage": None,
                "context_type": None,
                "evidence": None,
                "reason": f"Conflicting measurement values found for '{attribute_name}': {conflicts_str}."
            }

        # Unambiguous direct specification line found
        selected = direct_specs[0]
        assert selected["passage"] in selected["page_text"], (
            f"Internal error: Passage '{selected['passage']}' not found in cited page text"
        )
        evidence_dict = {
            "document_filename": selected["source_file"],
            "page_number": selected["page_number"],
            "supporting_passage": selected["passage"],
            "context_type": "passage"
        }
        return {
            **base_response,
            "status": "evidence_found",
            "retrieval_status": "evidence_found",
            "document_filename": selected["source_file"],
            "page_number": selected["page_number"],
            "evidence_passage": selected["passage"],
            "context_type": "passage",
            "evidence": evidence_dict,
            "reason": f"Found unambiguous direct measurement passage on page {selected['page_number']} of {selected['source_file']}."
        }

    # Requirement 3 Fallback: No direct specification line found -> search for pages mentioning attribute_name
    matching_pages = []
    for doc in matching_docs:
        source_file = doc.get("source_file", "unknown.pdf")
        for page in sorted(doc.get("pages", []), key=lambda p: p.get("page_number", 1)):
            p_num = page.get("page_number", 1)
            p_text = page.get("text", "")
            if re.search(rf'\b{re.escape(attribute_name)}\b', p_text, re.IGNORECASE):
                matching_pages.append({
                    "source_file": source_file,
                    "page_number": p_num,
                    "page_text": p_text
                })

    if not matching_pages:
        return {
            **base_response,
            "status": "insufficient_evidence",
            "retrieval_status": "insufficient_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "context_type": None,
            "evidence": None,
            "reason": f"No measurement evidence found for attribute '{attribute_name}' in matching document(s)."
        }

    # Extract verbatim section or full page context from eligible page
    selected_page = matching_pages[0]
    context_text, context_type = extract_section_or_page(selected_page["page_text"], attribute_name)

    assert context_text in selected_page["page_text"], (
        f"Internal error: Context '{context_text[:40]}...' not found in cited page text"
    )

    evidence_dict = {
        "document_filename": selected_page["source_file"],
        "page_number": selected_page["page_number"],
        "supporting_passage": context_text,
        "context_type": context_type
    }

    return {
        **base_response,
        "status": "evidence_found",
        "retrieval_status": "evidence_found",
        "document_filename": selected_page["source_file"],
        "page_number": selected_page["page_number"],
        "evidence_passage": context_text,
        "context_type": context_type,
        "evidence": evidence_dict,
        "reason": f"Found relevant {context_type} containing '{attribute_name}' on page {selected_page['page_number']} of {selected_page['source_file']}."
    }


def main():
    parser = argparse.ArgumentParser(description="Deterministic evidence retrieval baseline.")
    parser.add_argument("record_path", type=Path, help="Path to input record JSON")
    parser.add_argument(
        "--extracted-dir",
        type=Path,
        default=None,
        help="Path to directory containing extracted documents (default: data/extracted)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write output JSON result"
    )
    args = parser.parse_args()

    try:
        result = retrieve_evidence(args.record_path, extracted_dir=args.extracted_dir)
        output_str = json.dumps(result, indent=2, ensure_ascii=False)
        print(output_str)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str + "\n")

    except Exception as exc:
        print(f"Error during retrieval: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
