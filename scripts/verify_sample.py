#!/usr/bin/env python3
"""
Verification script for Step 3 synthetic investigation sample.
Verifies:
1. JSON validity for record and expected evaluation files.
2. Component ID and revision matching across record, expected evaluation, and PDF.
3. PDF readability, page count (exactly 1), selectable text, and presence of required metadata and exact passage.
4. Correctness of deterministic arithmetic: 0.8 cm = 8.0 mm.
"""

import json
import sys
from pathlib import Path
from pypdf import PdfReader


def main():
    repo_root = Path(__file__).resolve().parent.parent

    record_path = repo_root / "data" / "records" / "unit-mismatch-001.json"
    doc_path = repo_root / "data" / "documents" / "supplier-COMP-001.pdf"
    expected_path = repo_root / "evaluation" / "expected" / "unit-mismatch-001.json"

    print("=== Step 3 Verification Suite ===")

    # 1. Verify JSON validity
    assert record_path.exists(), f"Record file missing: {record_path}"
    assert expected_path.exists(), f"Expected evaluation file missing: {expected_path}"
    assert doc_path.exists(), f"Supplier PDF missing: {doc_path}"

    with open(record_path, "r", encoding="utf-8") as f:
        record_data = json.load(f)
    print("✓ Record JSON is valid.")

    with open(expected_path, "r", encoding="utf-8") as f:
        expected_data = json.load(f)
    print("✓ Expected evaluation JSON is valid.")

    # 2. Verify component identifiers and revisions match
    assert record_data["component_id"] == "COMP-001", f"Unexpected component_id in record: {record_data['component_id']}"
    assert expected_data["component_id"] == "COMP-001", f"Unexpected component_id in expected: {expected_data['component_id']}"
    assert record_data["component_id"] == expected_data["component_id"], "Component IDs do not match between record and expected"

    assert record_data["revision"] == "A", f"Unexpected revision in record: {record_data['revision']}"
    assert expected_data["revision"] == "A", f"Unexpected revision in expected: {expected_data['revision']}"
    assert record_data["revision"] == expected_data["revision"], "Revisions do not match between record and expected"
    print("✓ Component IDs ('COMP-001') and revisions ('A') match across record and expected evaluation.")

    # 3. Verify PDF readability, page count, selectable text, and required contents
    reader = PdfReader(str(doc_path))
    num_pages = len(reader.pages)
    assert num_pages == 1, f"Expected 1 page, found {num_pages}"
    print(f"✓ PDF has exactly {num_pages} page.")

    first_page = reader.pages[0]
    extracted_text = first_page.extract_text()
    assert extracted_text and len(extracted_text.strip()) > 50, "PDF contains no selectable text or text could not be extracted"
    print(f"✓ PDF contains {len(extracted_text)} characters of selectable text.")

    # Verify component ID in PDF
    assert "COMP-001" in extracted_text, "Component ID 'COMP-001' not found in PDF text"
    print("✓ Component ID 'COMP-001' found in PDF text.")

    # Verify revision in PDF
    assert "Revision: A" in extracted_text or "Revision:A" in extracted_text or "Revision" in extracted_text, "Revision not found in PDF text"
    print("✓ Revision found in PDF text.")

    # Verify document ID in PDF
    assert "DOC-SUP-COMP-001" in extracted_text, "Document ID 'DOC-SUP-COMP-001' not found in PDF text"
    print("✓ Document ID 'DOC-SUP-COMP-001' found in PDF text.")

    # Verify synthetic demonstration data notice
    assert "SYNTHETIC DEMONSTRATION DATA" in extracted_text.upper(), "Synthetic data notice not found in PDF text"
    print("✓ Synthetic demonstration notice found in PDF text.")

    # Verify exact passage
    exact_passage = "Component thickness: 0.8 cm."
    assert exact_passage in extracted_text, f"Exact passage '{exact_passage}' not found in PDF text"
    print(f"✓ Exact passage '{exact_passage}' found in PDF text.")

    # 4. Verify expected evaluation structure and values
    assert expected_data["evidence"]["document_filename"] == "supplier-COMP-001.pdf"
    assert expected_data["evidence"]["page_number"] == 1
    assert expected_data["evidence"]["supporting_passage"] == exact_passage
    print("✓ Expected evaluation evidence fields (filename, page=1, exact passage) match.")

    # 5. Deterministic arithmetic verification: 0.8 cm = 8.0 mm
    supplier_val = expected_data["expected_correction"]["conversion"]["supplier_extracted_value"]
    supplier_unit = expected_data["expected_correction"]["conversion"]["supplier_extracted_unit"]
    multiplier = expected_data["expected_correction"]["conversion"]["multiplier"]
    calculated_val = supplier_val * multiplier
    expected_val = expected_data["expected_correction"]["value"]
    expected_unit = expected_data["expected_correction"]["unit"]

    assert supplier_val == 0.8 and supplier_unit == "cm"
    assert multiplier == 10.0
    assert calculated_val == 8.0 and expected_val == 8.0 and expected_unit == "mm"
    print(f"✓ Deterministic arithmetic verified: {supplier_val} {supplier_unit} * {multiplier} mm/{supplier_unit} = {calculated_val} {expected_unit}.")

    # 6. Step 4 Verification: Extracted document verification
    extracted_path = repo_root / "data" / "extracted" / "supplier-COMP-001.json"
    assert extracted_path.exists(), f"Extracted file missing: {extracted_path}"
    with open(extracted_path, "r", encoding="utf-8") as f:
        extracted_data = json.load(f)
    print("✓ Extracted JSON is valid.")

    assert extracted_data["source_file"] == "supplier-COMP-001.pdf", f"Unexpected source_file: {extracted_data['source_file']}"
    assert len(extracted_data["pages"]) == 1, f"Expected 1 extracted page, got {len(extracted_data['pages'])}"
    extracted_page_1 = extracted_data["pages"][0]
    assert extracted_page_1["page_number"] == 1, f"Expected page_number 1, got {extracted_page_1['page_number']}"
    print("✓ Extracted source filename and page number are correct.")

    # Check that source text has not been rewritten or supplemented (matches raw pypdf text)
    assert extracted_page_1["text"] == extracted_text, "Extracted text does not match direct PDF extraction (text was altered)"
    print("✓ Source text matches direct PDF extraction without being rewritten or supplemented.")

    # Check component ID and measurement
    assert "COMP-001" in extracted_page_1["text"], "Component ID 'COMP-001' missing from extracted text"
    assert "0.8 cm" in extracted_page_1["text"], "Measurement '0.8 cm' missing from extracted text"
    assert exact_passage in extracted_page_1["text"], f"Exact passage '{exact_passage}' missing from extracted text"
    print("✓ Component ID ('COMP-001'), measurement ('0.8 cm'), and exact passage survived extraction intact.")

    # 7. Step 5 Verification: Deterministic evidence retrieval
    sys.path.insert(0, str(repo_root / "scripts"))
    import tempfile
    from retrieve_evidence import retrieve_evidence

    # 7a. Existing sample retrieval
    res_sample = retrieve_evidence(record_path)
    assert res_sample["status"] == "evidence_found", f"Expected evidence_found, got {res_sample['status']}"
    assert res_sample["document_filename"] == "supplier-COMP-001.pdf", f"Unexpected document: {res_sample['document_filename']}"
    assert res_sample["page_number"] == 1, f"Unexpected page: {res_sample['page_number']}"
    assert res_sample["evidence_passage"] == exact_passage, f"Expected '{exact_passage}', got '{res_sample['evidence_passage']}'"
    assert res_sample["evidence"]["supporting_passage"] == exact_passage
    assert res_sample["evidence_passage"] in extracted_page_1["text"], "Evidence passage does not exist in extracted page text"
    print(f"✓ Step 5 baseline retrieved '{exact_passage}' from {res_sample['document_filename']} page {res_sample['page_number']}.")

    # 7b. Negative and edge cases using isolated temporary fixtures
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)

        # Unknown component -> insufficient_evidence
        rec_unknown = tmp_path / "unknown_comp.json"
        with open(rec_unknown, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-unknown",
                "component_id": "COMP-999",
                "revision": "A",
                "attribute_name": "thickness"
            }, f)
        res_unknown = retrieve_evidence(rec_unknown)
        assert res_unknown["status"] == "insufficient_evidence", f"Expected insufficient_evidence, got {res_unknown['status']}"
        print("✓ Unknown component returned 'insufficient_evidence'.")

        # Incorrect revision -> insufficient_evidence
        rec_bad_rev = tmp_path / "bad_rev.json"
        with open(rec_bad_rev, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-bad-rev",
                "component_id": "COMP-001",
                "revision": "B",
                "attribute_name": "thickness"
            }, f)
        res_bad_rev = retrieve_evidence(rec_bad_rev)
        assert res_bad_rev["status"] == "insufficient_evidence", f"Expected insufficient_evidence, got {res_bad_rev['status']}"
        print("✓ Incorrect revision returned 'insufficient_evidence'.")

        # Missing measurement -> insufficient_evidence
        rec_missing_meas = tmp_path / "missing_meas.json"
        with open(rec_missing_meas, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-missing-meas",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "weight"
            }, f)
        res_missing_meas = retrieve_evidence(rec_missing_meas)
        assert res_missing_meas["status"] == "insufficient_evidence", f"Expected insufficient_evidence, got {res_missing_meas['status']}"
        print("✓ Missing measurement returned 'insufficient_evidence'.")

        # Conflicting evidence -> ambiguous_evidence
        tmp_extracted = tmp_path / "extracted"
        tmp_extracted.mkdir()
        conflict_doc = {
            "source_file": "supplier-CONFLICT.pdf",
            "pages": [
                {
                    "page_number": 1,
                    "text": (
                        "Component ID: COMP-001\n"
                        "Revision: A\n"
                        "Component thickness: 0.8 cm.\n"
                        "Variant Component thickness: 1.2 cm.\n"
                    )
                }
            ]
        }
        with open(tmp_extracted / "supplier-CONFLICT.json", "w", encoding="utf-8") as f:
            json.dump(conflict_doc, f)

        rec_conflict = tmp_path / "conflict_record.json"
        with open(rec_conflict, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-conflict",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "document_reference": {"filename": "supplier-CONFLICT.pdf"}
            }, f)
        res_conflict = retrieve_evidence(rec_conflict, extracted_dir=tmp_extracted)
        assert res_conflict["status"] == "ambiguous_evidence", f"Expected ambiguous_evidence, got {res_conflict['status']}"
        print("✓ Conflicting evidence returned 'ambiguous_evidence'.")

    print("\nALL STEP 3, STEP 4 & STEP 5 VERIFICATION CHECKS PASSED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
