#!/usr/bin/env python3
"""
Deterministic evidence retrieval baseline for Engineering Data Investigation Copilot.

Step 5 implementation:
- Reads a supplied engineering record JSON and extracted documents in data/extracted/ only.
- Identifies component ID, revision, and attribute name from record.
- Matches component ID and revision explicitly in document content (no partial ID matches).
- Finds matching measurement passages for the requested attribute.
- Resolves conflicts: returns 'ambiguous_evidence' if conflicting measurements exist.
- Returns 'insufficient_evidence' if no matching component, revision, or measurement is found.
- Returns 'evidence_found' with source PDF filename, 1-indexed page number, and exact passage.
- Guarantees returned passage is copied verbatim from the extracted page text.
- Never reads evaluation/expected/ or project documentation.
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


def is_direct_specification_line(line: str, attribute_name: str) -> bool:
    """Check if a line is a direct specification statement for the attribute.
    
    Matches lines such as:
    - 'Component thickness: 0.8 cm.'
    - 'thickness: 0.8 cm'
    - 'thickness = 0.8 cm'
    - 'Overall component thickness: 0.8 cm ± 0.02 cm.'
    """
    pattern = (
        rf'^(?:[A-Za-z0-9_-]+\s+)*{re.escape(attribute_name)}\s*(?:[:=]|\bis\b)\s*'
        rf'\d+(?:\.\d+)?\s*[a-zA-Zµ°Ω%]+(?:\s*[±+/-]\s*\d+(?:\.\d+)?\s*[a-zA-Zµ°Ω%]+)?[.;]?$'
    )
    return bool(re.match(pattern, line.strip(), re.IGNORECASE))


def extract_candidate_passages(page_text: str, attribute_name: str) -> List[Dict[str, Any]]:
    """Extract candidate passages from a page's text for the requested attribute.
    
    Returns candidate dictionaries containing:
    - passage: verbatim string from text
    - val: float numeric nominal measurement
    - unit: lowercase unit string
    - is_direct: bool indicating whether line is a direct specification statement
    """
    candidates = []
    lines = page_text.splitlines()

    for line in lines:
        cleaned_line = line.strip()
        if not cleaned_line:
            continue

        if re.search(rf'\b{re.escape(attribute_name)}\b', cleaned_line, re.IGNORECASE):
            # Extract nominal measurement: attribute followed by number and unit
            pattern_fwd = rf'\b{re.escape(attribute_name)}\b[^\n.!?]*?(?:[:=]|\bis\b)?\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)'
            m = re.search(pattern_fwd, cleaned_line, re.IGNORECASE)

            # Or measurement followed by attribute (e.g., '0.8 cm thickness')
            if not m:
                pattern_rev = rf'(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)\s+(?:[A-Za-z0-9_-]+\s+)*{re.escape(attribute_name)}'
                m = re.search(pattern_rev, cleaned_line, re.IGNORECASE)

            if m:
                val = float(m.group(1))
                unit = m.group(2).lower()
                direct = is_direct_specification_line(cleaned_line, attribute_name)

                # Ensure passage is a verbatim substring of page_text
                # If cleaned_line exists in page_text, use it; otherwise locate exact slice
                passage_str = cleaned_line if cleaned_line in page_text else line
                candidates.append({
                    "passage": passage_str,
                    "val": val,
                    "unit": unit,
                    "is_direct": direct
                })

    return candidates


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
            "evidence": None,
            "reason": f"Extracted documents directory '{extracted_dir}' does not exist."
        }

    # Locate candidate documents in data/extracted/
    # If record references a specific document filename, prioritize it
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
    # If no specific candidate found from reference, scan all extracted documents in sorted order
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
            "evidence": None,
            "reason": f"No extracted JSON documents found in '{extracted_dir}'."
        }

    matching_docs = []
    component_found_anywhere = False

    for json_file in candidate_files:
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                doc_data = json.load(f)
        except Exception as exc:
            continue

        pages = doc_data.get("pages", [])
        full_text = "\n".join(p.get("text", "") for p in pages)

        # Requirement 3: Match component ID and revision explicitly in document content
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
            "evidence": None,
            "reason": f"Document content matches component '{component_id}' but revision '{revision}' was not confirmed."
        }

    # Search for measurement passages across matching documents and pages
    all_candidates = []
    for doc in matching_docs:
        source_file = doc.get("source_file", "unknown.pdf")
        for page in sorted(doc.get("pages", []), key=lambda p: p.get("page_number", 1)):
            p_num = page.get("page_number", 1)
            p_text = page.get("text", "")
            page_candidates = extract_candidate_passages(p_text, attribute_name)
            for c in page_candidates:
                all_candidates.append({
                    **c,
                    "source_file": source_file,
                    "page_number": p_num,
                    "page_text": p_text
                })

    if not all_candidates:
        return {
            **base_response,
            "status": "insufficient_evidence",
            "retrieval_status": "insufficient_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "evidence": None,
            "reason": f"No measurement passages found for attribute '{attribute_name}' in matching document(s)."
        }

    # Evaluate consistency across candidates
    # Group by measurement value and unit
    distinct_measurements = {(c["val"], c["unit"]) for c in all_candidates}

    # Requirement 5: If matching passages conflict, return ambiguous_evidence
    if len(distinct_measurements) > 1:
        conflicts_str = ", ".join(f"{val} {unit}" for val, unit in sorted(distinct_measurements))
        return {
            **base_response,
            "status": "ambiguous_evidence",
            "retrieval_status": "ambiguous_evidence",
            "document_filename": None,
            "page_number": None,
            "evidence_passage": None,
            "evidence": None,
            "reason": f"Conflicting measurement values found for '{attribute_name}': {conflicts_str}."
        }

    # All candidate passages agree on the exact same nominal measurement
    # Prioritize direct specification lines over indirect prose mentions
    direct_candidates = [c for c in all_candidates if c["is_direct"]]
    selected = direct_candidates[0] if direct_candidates else all_candidates[0]

    # Verify that the quote exists on the cited extracted page
    assert selected["passage"] in selected["page_text"], (
        f"Internal error: Passage '{selected['passage']}' not found in cited page text"
    )

    evidence_dict = {
        "document_filename": selected["source_file"],
        "page_number": selected["page_number"],
        "supporting_passage": selected["passage"]
    }

    return {
        **base_response,
        "status": "evidence_found",
        "retrieval_status": "evidence_found",
        "document_filename": selected["source_file"],
        "page_number": selected["page_number"],
        "evidence_passage": selected["passage"],
        "evidence": evidence_dict,
        "reason": f"Found unambiguous measurement passage on page {selected['page_number']} of {selected['source_file']}."
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
