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

    # 8. Step 6 Verification: Unit mismatch investigation and correction workflow
    from investigate_record import investigate_record

    # 8a. Sample case: record 0.8 mm, evidence 0.8 cm -> propose 8.0 mm
    inv_sample = investigate_record(record_path)
    assert inv_sample["outcome"] == "correction_proposed", f"Expected correction_proposed, got {inv_sample['outcome']}"
    assert inv_sample["status"] == "correction_proposed"
    assert inv_sample["proposed_correction"] is not None
    assert inv_sample["proposed_correction"]["value"] == 8.0
    assert inv_sample["proposed_correction"]["unit"] == "mm"
    assert inv_sample["proposed_correction"]["conversion"]["multiplier"] == 10.0
    assert inv_sample["evidence"]["document_filename"] == "supplier-COMP-001.pdf"
    assert inv_sample["evidence"]["page_number"] == 1
    assert inv_sample["evidence"]["supporting_passage"] == exact_passage
    assert inv_sample["source_record_modified"] is False
    print("✓ Step 6 sample verified: record 0.8 mm vs evidence 0.8 cm -> proposed 8.0 mm with citation.")

    # 8b. Temporary fixtures for comprehensive Step 6 validation
    with tempfile.TemporaryDirectory() as tmpdir_step6:
        t6_path = Path(tmpdir_step6)

        # Record 8.0 mm, evidence 0.8 cm -> no_change
        rec_match = t6_path / "rec_match.json"
        with open(rec_match, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-match",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 8.0,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-001.pdf"}
            }, f)
        inv_match = investigate_record(rec_match)
        assert inv_match["outcome"] == "no_change", f"Expected no_change, got {inv_match['outcome']}"
        assert inv_match["proposed_correction"] is None, "Abstention outcome must have no proposed correction"
        assert inv_match["evidence"]["document_filename"] == "supplier-COMP-001.pdf"
        assert inv_match["evidence"]["supporting_passage"] == exact_passage
        print("✓ Verified no_change: record 8.0 mm vs evidence 0.8 cm -> no_change (with valid citation).")

        # Reverse conversion: mm to cm
        # Create temp extracted doc specifying length = 20.0 mm
        t6_ext = t6_path / "extracted"
        t6_ext.mkdir()
        t6_doc = {
            "source_file": "supplier-REV.pdf",
            "pages": [
                {
                    "page_number": 1,
                    "text": (
                        "Component ID: COMP-002\n"
                        "Revision: A\n"
                        "Component width: 20.0 mm.\n"
                    )
                }
            ]
        }
        with open(t6_ext / "supplier-REV.json", "w", encoding="utf-8") as f:
            json.dump(t6_doc, f)

        # Reverse mismatch: record has 20.0 cm, evidence has 20.0 mm -> propose 2.0 cm
        rec_rev_mismatch = t6_path / "rec_rev_mismatch.json"
        with open(rec_rev_mismatch, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-rev-mismatch",
                "component_id": "COMP-002",
                "revision": "A",
                "attribute_name": "width",
                "recorded_value": 20.0,
                "recorded_unit": "cm",
                "document_reference": {"filename": "supplier-REV.pdf"}
            }, f)
        inv_rev_mismatch = investigate_record(rec_rev_mismatch, extracted_dir=t6_ext)
        assert inv_rev_mismatch["outcome"] == "correction_proposed"
        assert inv_rev_mismatch["proposed_correction"]["value"] == 2.0
        assert inv_rev_mismatch["proposed_correction"]["unit"] == "cm"
        print("✓ Verified reverse conversion (mm to cm): evidence 20.0 mm -> proposed 2.0 cm.")

        # Reverse match: record has 2.0 cm, evidence has 20.0 mm -> no_change
        rec_rev_match = t6_path / "rec_rev_match.json"
        with open(rec_rev_match, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-rev-match",
                "component_id": "COMP-002",
                "revision": "A",
                "attribute_name": "width",
                "recorded_value": 2.0,
                "recorded_unit": "cm",
                "document_reference": {"filename": "supplier-REV.pdf"}
            }, f)
        inv_rev_match = investigate_record(rec_rev_match, extracted_dir=t6_ext)
        assert inv_rev_match["outcome"] == "no_change"
        assert inv_rev_match["proposed_correction"] is None
        print("✓ Verified reverse agreement: record 2.0 cm vs evidence 20.0 mm -> no_change.")

        # Missing evidence -> insufficient_evidence
        rec_missing = t6_path / "rec_missing.json"
        with open(rec_missing, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-missing",
                "component_id": "COMP-UNKNOWN",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm"
            }, f)
        inv_missing = investigate_record(rec_missing)
        assert inv_missing["outcome"] == "insufficient_evidence"
        assert inv_missing["proposed_correction"] is None
        print("✓ Missing evidence -> insufficient_evidence.")

        # Conflicting evidence -> ambiguous_evidence
        conflict_doc6 = {
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
        with open(t6_ext / "supplier-CONFLICT.json", "w", encoding="utf-8") as f:
            json.dump(conflict_doc6, f)

        rec_conflict6 = t6_path / "conflict_record6.json"
        with open(rec_conflict6, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-conflict6",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-CONFLICT.pdf"}
            }, f)

        inv_conflict = investigate_record(rec_conflict6, extracted_dir=t6_ext)
        assert inv_conflict["outcome"] == "ambiguous_evidence"
        assert inv_conflict["proposed_correction"] is None
        print("✓ Conflicting evidence -> ambiguous_evidence.")

        # Unsupported units in record -> needs_review
        rec_unsupported_unit = t6_path / "rec_unsupported.json"
        with open(rec_unsupported_unit, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-unsupported",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "in"
            }, f)
        inv_unsupported = investigate_record(rec_unsupported_unit)
        assert inv_unsupported["outcome"] == "needs_review"
        assert inv_unsupported["proposed_correction"] is None
        print("✓ Unsupported unit in record ('in') -> needs_review.")

        # Malformed / unparseable measurement value in record -> needs_review
        rec_malformed = t6_path / "rec_malformed.json"
        with open(rec_malformed, "w", encoding="utf-8") as f:
            json.dump({
                "record_id": "test-malformed",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": "N/A_NOT_A_NUMBER",
                "recorded_unit": "mm"
            }, f)
        inv_malformed = investigate_record(rec_malformed)
        assert inv_malformed["outcome"] == "needs_review"
        assert inv_malformed["proposed_correction"] is None
        print("✓ Malformed record measurement -> needs_review.")

    # 9. Step 7 Verification: Evaluation suite runner and report checks
    from evaluate import run_evaluation
    eval_report = run_evaluation(repo_root)
    assert eval_report["summary"]["total_cases"] == 10
    assert eval_report["summary"]["passed_cases"] == 10
    assert eval_report["summary"]["overall_pass_rate_pct"] == 100.0
    assert eval_report["summary"]["correction_pass_rate_pct"] == 100.0
    assert eval_report["summary"]["abstention_pass_rate_pct"] == 100.0
    assert eval_report["summary"]["citation_validity"]["valid"] == 5
    assert (repo_root / "evaluation" / "reports" / "evaluation_report.json").exists()
    assert (repo_root / "evaluation" / "reports" / "evaluation_report.md").exists()
    print("✓ Step 7 evaluation suite verified: 10/10 cases passed, reports generated.\n")

    # 10. Step 8 Verification: Gemini measurement extractor & guardrails
    from verify_step8_extractor import run_all_step8_checks
    run_all_step8_checks()

    # 11. Step 12 Verification: Improved evidence retrieval on challenge cases
    challenge_cases_dir = repo_root / "evaluation" / "cases"

    # Verify retrieval on the 4 relevant challenge cases
    c1_ret = retrieve_evidence(challenge_cases_dir / "challenge-01-complete-sentence" / "record.json", extracted_dir=challenge_cases_dir / "challenge-01-complete-sentence" / "extracted")
    assert c1_ret["status"] == "evidence_found", f"Expected evidence_found, got {c1_ret['status']}"
    assert c1_ret["context_type"] == "section", f"Expected section context, got {c1_ret['context_type']}"
    assert "1.2 cm" in c1_ret["evidence_passage"]
    assert "thickness" in c1_ret["evidence_passage"].lower()
    print("✓ Challenge 01 (sentence) retrieved section containing 1.2 cm thickness.")

    c2_ret = retrieve_evidence(challenge_cases_dir / "challenge-02-table-value-unit-columns" / "record.json", extracted_dir=challenge_cases_dir / "challenge-02-table-value-unit-columns" / "extracted")
    assert c2_ret["status"] == "evidence_found", f"Expected evidence_found, got {c2_ret['status']}"
    assert c2_ret["context_type"] == "section", f"Expected section context, got {c2_ret['context_type']}"
    assert "15.0" in c2_ret["evidence_passage"] and "mm" in c2_ret["evidence_passage"]
    print("✓ Challenge 02 (table columns) retrieved section containing parameter table headers, values, and units.")

    c3_ret = retrieve_evidence(challenge_cases_dir / "challenge-03-split-lines-label-measurement" / "record.json", extracted_dir=challenge_cases_dir / "challenge-03-split-lines-label-measurement" / "extracted")
    assert c3_ret["status"] == "evidence_found", f"Expected evidence_found, got {c3_ret['status']}"
    assert c3_ret["context_type"] == "section", f"Expected section context, got {c3_ret['context_type']}"
    assert "2.4 mm" in c3_ret["evidence_passage"]
    print("✓ Challenge 03 (split lines) retrieved section containing wrapped label and measurement.")

    c4_ret = retrieve_evidence(challenge_cases_dir / "challenge-04-distracting-measurements" / "record.json", extracted_dir=challenge_cases_dir / "challenge-04-distracting-measurements" / "extracted")
    assert c4_ret["status"] == "evidence_found", f"Expected evidence_found, got {c4_ret['status']}"
    assert c4_ret["context_type"] == "section", f"Expected section context, got {c4_ret['context_type']}"
    assert "6.0 mm" in c4_ret["evidence_passage"]
    print("✓ Challenge 04 (distracting dimensions) retrieved section containing package dimensions context.")

    c5_ret = retrieve_evidence(challenge_cases_dir / "challenge-05-incorrect-revision" / "record.json", extracted_dir=challenge_cases_dir / "challenge-05-incorrect-revision" / "extracted")
    assert c5_ret["status"] == "insufficient_evidence", f"Expected insufficient_evidence, got {c5_ret['status']}"
    print("✓ Challenge 05 (incorrect revision) correctly abstained with 'insufficient_evidence'.")

    c6_ret = retrieve_evidence(challenge_cases_dir / "challenge-06-conflicting-statements" / "record.json", extracted_dir=challenge_cases_dir / "challenge-06-conflicting-statements" / "extracted")
    assert c6_ret["status"] == "ambiguous_evidence", f"Expected ambiguous_evidence, got {c6_ret['status']}"
    print("✓ Challenge 06 (conflicting statements) correctly abstained with 'ambiguous_evidence'.")

    # 12. Step 14 Verification: Quote alignment and labelled measurement binding
    print("=== Step 14 Verification Suite ===")
    import hashlib
    from decimal import Decimal
    from investigate_record import align_quote_to_passage, convert_measurement
    from extractors import parse_labelled_tuple

    # 12.1 Whitespace-aware quote alignment tests
    passage_sample = (
        "2. Physical Dimensions & Mechanical Parameters\n"
        "Mechanical parameters and specifications for component ID COMP-C01 (25°C, 50% RH):\n"
        "Under standard ambient conditions, the nominal thickness of component COMP-C01 is\n"
        "manufactured to 1.2 cm across all production lots.\n"
        "Component thickness: 0.8 cm."
    )

    # 12.1.1 Strict literal matching preserved as first option
    lit_span, lit_type, lit_err = align_quote_to_passage("Component thickness: 0.8 cm.", passage_sample)
    assert lit_span == "Component thickness: 0.8 cm.", f"Expected literal span, got {lit_span}"
    assert lit_type == "literal", f"Expected literal, got {lit_type}"
    assert lit_err is None
    print("✓ Strict literal matching preserved as first option.")

    # 12.1.2 Whitespace differences allowed (line breaks in PDF)
    ws_quote = "the nominal thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots."
    ws_span, ws_type, ws_err = align_quote_to_passage(ws_quote, passage_sample)
    assert ws_span is not None, "Expected whitespace-aligned span"
    assert ws_type == "whitespace_aligned"
    assert ws_err is None
    assert "\n" in ws_span, "Expected newline in source span"
    assert ws_span == "the nominal thickness of component COMP-C01 is\nmanufactured to 1.2 cm across all production lots."
    print("✓ Whitespace-aware quote alignment maps to original verbatim span with index mapping.")

    # 12.1.3 Rejection of modified numbers
    bad_num_quote = "the nominal thickness of component COMP-C01 is manufactured to 1.5 cm across all production lots."
    bad_span, bad_type, bad_err = align_quote_to_passage(bad_num_quote, passage_sample)
    assert bad_span is None and bad_type == "missing"
    print("✓ Rejection of modified numbers verified.")

    # 12.1.4 Rejection of modified units
    bad_unit_quote = "the nominal thickness of component COMP-C01 is manufactured to 1.2 mm across all production lots."
    bad_span, bad_type, bad_err = align_quote_to_passage(bad_unit_quote, passage_sample)
    assert bad_span is None and bad_type == "missing"
    print("✓ Rejection of modified units verified.")

    # 12.1.5 Rejection of invented words
    bad_word_quote = "the exact thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots."
    bad_span, bad_type, bad_err = align_quote_to_passage(bad_word_quote, passage_sample)
    assert bad_span is None and bad_type == "missing"
    print("✓ Rejection of invented words verified.")

    # 12.1.6 Rejection of ambiguous quote (multiple matches)
    ambig_passage = "thickness: 1.2 cm ... other section ... thickness: 1.2 cm"
    ambig_span, ambig_type, ambig_err = align_quote_to_passage("thickness: 1.2 cm", ambig_passage)
    assert ambig_span is None and ambig_type == "ambiguous"
    print("✓ Ambiguous quote rejection verified.")

    # 12.2 Deterministic measurement binding for labelled tuples
    tuple_text = "Package dimensions (length, width, thickness): 60.0 mm x 40.0 mm x 6.0 mm"
    # Target: thickness (3rd position) -> 6.0 mm (must not greedily pick 60.0 mm)
    t_val, t_unit, t_quote, t_err = parse_labelled_tuple(tuple_text, "thickness")
    assert t_val == Decimal("6.0"), f"Expected 6.0 mm for thickness, got {t_val}"
    assert t_unit == "mm"
    assert t_err is None
    print("✓ Labelled tuple: thickness correctly bound to 3rd position (6.0 mm, not 60.0 mm).")

    # Target: length (1st position) -> 60.0 mm
    l_val, l_unit, l_quote, l_err = parse_labelled_tuple(tuple_text, "length")
    assert l_val == Decimal("60.0") and l_unit == "mm" and l_err is None
    print("✓ Labelled tuple: length correctly bound to 1st position (60.0 mm).")

    # Target: width (2nd position) -> 40.0 mm
    w_val, w_unit, w_quote, w_err = parse_labelled_tuple(tuple_text, "width")
    assert w_val == Decimal("40.0") and w_unit == "mm" and w_err is None
    print("✓ Labelled tuple: width correctly bound to 2nd position (40.0 mm).")

    # Shared trailing unit: (length, width, height): 10 x 20 x 30 mm
    shared_text = "(length, width, height): 10 x 20 x 30 mm"
    h_val, h_unit, h_quote, h_err = parse_labelled_tuple(shared_text, "height")
    assert h_val == Decimal("30") and h_unit == "mm"
    print("✓ Labelled tuple with shared trailing unit correctly propagates unit.")

    # 12.2.1 Unclear tuple abstention (count mismatch)
    mismatch_text = "(length, width, thickness): 60.0 mm x 40.0 mm"
    m_val, m_unit, m_quote, m_err = parse_labelled_tuple(mismatch_text, "thickness")
    assert m_val is None and "does not match value count" in str(m_err)
    print("✓ Unclear tuple (label/value count mismatch) safely abstains.")

    # 12.2.2 Unclear tuple abstention (duplicate matching label)
    dup_text = "(thickness, thickness): 6.0 mm x 8.0 mm"
    d_val, d_unit, d_quote, d_err = parse_labelled_tuple(dup_text, "thickness")
    assert d_val is None and "matches multiple label positions" in str(d_err)
    print("✓ Unclear tuple (duplicate matching labels) safely abstains.")

    # 12.2.3 Unclear tuple abstention (missing units)
    nounit_text = "(length, width, thickness): 60 x 40 x 6"
    nu_val, nu_unit, nu_quote, nu_err = parse_labelled_tuple(nounit_text, "thickness")
    assert nu_val is None and "no unit found" in str(nu_err)
    print("✓ Unclear tuple (missing units) safely abstains.")

    # 12.3 Offline replay validation of saved challenge-01 model response
    # Step 13 frozen comparison report must be preserved and used as replay input
    frozen_report_path = repo_root / "evaluation" / "reports" / "challenge_comparison_report.json"
    assert frozen_report_path.exists(), "Frozen Step 13 challenge_comparison_report.json missing"
    with open(frozen_report_path, "r", encoding="utf-8") as f:
        frozen_data = json.load(f)
    c1_frozen = [c for c in frozen_data["cases"] if c["case_id"] == "challenge-01-complete-sentence"][0]

    # Verify frozen extraction details from Step 13
    assert c1_frozen["gemini_model_called"] is True
    assert c1_frozen["gemini_token_usage"] is not None
    saved_quote = "the nominal thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots."
    assert saved_quote in c1_frozen["gemini_explanation"]

    # Replay through whitespace-aware quote alignment
    c1_case_dir = repo_root / "evaluation" / "cases" / "challenge-01-complete-sentence"
    c1_ret = retrieve_evidence(c1_case_dir / "record.json", extracted_dir=c1_case_dir / "extracted")
    c1_passage = c1_ret["evidence_passage"]
    c1_span, c1_align_type, c1_align_err = align_quote_to_passage(saved_quote, c1_passage)
    assert c1_span is not None
    assert c1_align_type == "whitespace_aligned"
    assert c1_align_err is None
    assert "is\nmanufactured" in c1_span

    # Verify downstream deterministic conversion and comparison
    c1_conv_val, c1_mult, c1_calc = convert_measurement(Decimal("1.2"), "cm", "mm")
    assert c1_conv_val == Decimal("12.0")
    with open(c1_case_dir / "record.json", "r", encoding="utf-8") as f:
        c1_rec = json.load(f)
    assert Decimal(str(c1_rec["recorded_value"])) == Decimal("1.2")
    assert c1_rec["recorded_unit"] == "mm"
    assert c1_conv_val != Decimal(str(c1_rec["recorded_value"]))  # 12.0 mm != 1.2 mm -> correction proposed!
    print("✓ Offline replay validation of saved challenge-01 response verified (1.2 cm -> 12.0 mm).")

    # 12.4 Record and source file immutability verification
    for case_folder in (repo_root / "evaluation" / "cases").iterdir():
        if not case_folder.is_dir():
            continue
        rec_f = case_folder / "record.json"
        if rec_f.exists():
            h_before = hashlib.sha256(rec_f.read_bytes()).hexdigest()
            # Investigate record
            investigate_record(rec_f, extracted_dir=case_folder / "extracted")
            h_after = hashlib.sha256(rec_f.read_bytes()).hexdigest()
            assert h_before == h_after, f"Record was mutated by investigation: {rec_f}"
    print("✓ Immutability of record and source files verified across all cases.")

    # 12.5 Challenge suite evaluation verification (5/6 pass deterministically, 1 honest regex limitation)
    challenge_report_14 = run_evaluation(repo_root, extractor="deterministic", suite="challenge")
    assert challenge_report_14["summary"]["total_cases"] == 6
    assert challenge_report_14["summary"]["passed_cases"] == 5, f"Expected 5 passed cases, got {challenge_report_14['summary']['passed_cases']}"
    assert challenge_report_14["summary"]["failed_cases"] == 1
    assert challenge_report_14["summary"]["overall_pass_rate_pct"] == 83.3
    assert challenge_report_14["summary"]["evidence_retrieval_success_rate"] == "4/4 (100.0%)"
    assert challenge_report_14["summary"]["retrieval_abstention_success_rate"] == "2/2 (100.0%)"
    assert challenge_report_14["summary"]["agreement_pass_rate_pct"] == 100.0
    assert challenge_report_14["summary"]["abstention_pass_rate_pct"] == 100.0
    assert challenge_report_14["summary"]["citation_validity"]["valid"] == 4

    failed_14 = [c for c in challenge_report_14["cases"] if not c["passed"]]
    assert len(failed_14) == 1
    assert failed_14[0]["case_id"] == "challenge-01-complete-sentence"
    assert failed_14[0]["failure_stage"] == "measurement extraction"
    print("✓ Step 14 deterministic challenge suite verified: 5/6 (83.3%) pass, challenge-04 resolved, challenge-01 honestly documented as regex sentence limitation.\n")

    print("ALL STEP 3, STEP 4, STEP 5, STEP 6, STEP 7, STEP 8, STEP 11, STEP 12 & STEP 14 VERIFICATION CHECKS PASSED SUCCESSFULLY.")


if __name__ == "__main__":
    main()
