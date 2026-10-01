#!/usr/bin/env python3
"""
Generate the 10 synthetic evaluation cases for Step 7.

Creates:
- evaluation/cases/<case_id>/record.json
- evaluation/cases/<case_id>/documents/<pdf_filename>.pdf
- evaluation/cases/<case_id>/extracted/<extracted_filename>.json
- evaluation/expected/<case_id>.json (explicitly authored expectations)

Isolation:
Each case has an isolated documents/ and extracted/ corpus directory.
Expected outcomes are stored separately under evaluation/expected/.
"""

import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_documents import extract_pdf


def build_synthetic_pdf(
    output_path: Path,
    component_id: str,
    revision: str,
    document_id: str,
    primary_passage: str,
    specs: List[List[str]],
    secondary_passage: Optional[str] = None
):
    """Generate a single-page synthetic supplier datasheet PDF using ReportLab."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=36,
        bottomMargin=36
    )

    styles = getSampleStyleSheet()

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=8
    )

    banner_style = ParagraphStyle(
        'SyntheticBanner',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor('#DC2626'),
        alignment=1
    )

    heading2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=8,
        spaceAfter=4
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=13.5,
        textColor=colors.HexColor('#334155')
    )

    callout_style = ParagraphStyle(
        'KeyPassage',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=4,
        spaceAfter=4
    )

    footer_style = ParagraphStyle(
        'FooterNote',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=10,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )

    elements = []

    # Banner
    banner_table = Table(
        [[Paragraph("SYNTHETIC DEMONSTRATION DATA — FOR TESTING AND EVALUATION ONLY", banner_style)]],
        colWidths=[504]
    )
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEE2E2')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#F87171')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 8))

    # Header
    elements.append(Paragraph("Apex Microelectronics Corp. — Supplier Datasheet", title_style))
    elements.append(Paragraph("Technical Product Specification & Interface Guidelines", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=8))

    # Metadata Table
    metadata_data = [
        [
            Paragraph(f"<b>Component ID:</b> {component_id}", body_style),
            Paragraph(f"<b>Revision:</b> {revision}", body_style)
        ],
        [
            Paragraph(f"<b>Document ID:</b> {document_id}", body_style),
            Paragraph("<b>Effective Date:</b> 2026-10-01", body_style)
        ],
        [
            Paragraph("<b>Part Description:</b> Precision Engineering Component", body_style),
            Paragraph("<b>Status:</b> Authoritative Supplier Release", body_style)
        ]
    ]
    meta_table = Table(metadata_data, colWidths=[252, 252])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 8))

    # Section 1: Overview
    elements.append(Paragraph("1. Product Overview", heading2_style))
    overview_text = (
        f"This document serves as the authoritative supplier technical specification for revision {revision} "
        f"of component {component_id}. All physical dimensions herein supersede preliminary notes."
    )
    elements.append(Paragraph(overview_text, body_style))
    elements.append(Spacer(1, 6))

    # Section 2: Physical Specifications
    elements.append(Paragraph("2. Physical Dimensions & Mechanical Parameters", heading2_style))
    intro_dim = f"Mechanical measurements for component ID {component_id} under standard test conditions (25°C, 50% RH):"
    elements.append(Paragraph(intro_dim, body_style))
    elements.append(Spacer(1, 4))

    # Primary passage
    elements.append(Paragraph(primary_passage, callout_style))

    if secondary_passage:
        elements.append(Paragraph(secondary_passage, callout_style))

    elements.append(Spacer(1, 4))

    # Specs table
    table_data = [[
        Paragraph("<b>Parameter</b>", body_style),
        Paragraph("<b>Nominal Value</b>", body_style),
        Paragraph("<b>Tolerance</b>", body_style),
        Paragraph("<b>Notes</b>", body_style)
    ]]
    for row in specs:
        table_data.append([
            Paragraph(row[0], body_style),
            Paragraph(row[1], body_style),
            Paragraph(row[2], body_style),
            Paragraph(row[3], body_style)
        ])

    spec_table = Table(table_data, colWidths=[120, 100, 90, 194])
    spec_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 3),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(spec_table)
    elements.append(Spacer(1, 8))

    # Section 3: Notice
    elements.append(Paragraph("3. Synthetic Demonstration Notice", heading2_style))
    notice_text = (
        "This datasheet is entirely synthetic demonstration data created for testing and verifying the "
        "Engineering Data Investigation Copilot benchmark suite."
    )
    elements.append(Paragraph(notice_text, body_style))
    elements.append(Spacer(1, 10))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=2, spaceAfter=6))
    elements.append(Paragraph(
        f"Page 1 of 1 | Document ID: {document_id} | Revision: {revision} | Synthetic Test Dataset",
        footer_style
    ))

    doc.build(elements)


def generate_all_cases(repo_root: Path):
    cases_dir = repo_root / "evaluation" / "cases"
    expected_dir = repo_root / "evaluation" / "expected"

    cases_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    # 10 Case Definitions
    case_specs = [
        # Case 1: correction cm -> mm
        {
            "case_id": "case-01-correction-cm-to-mm",
            "category": "correction",
            "description": "Recorded thickness = 0.8 mm vs datasheet thickness = 0.8 cm -> propose 8.0 mm.",
            "record": {
                "case_id": "case-01-correction-cm-to-mm",
                "record_id": "REC-01",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-001.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-001.pdf",
                "component_id": "COMP-001",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-001",
                "primary_passage": "Component thickness: 0.8 cm.",
                "specs": [
                    ["Length", "25.0 mm", "±0.1 mm", "Longitudinal axis"],
                    ["Width", "15.0 mm", "±0.1 mm", "Transverse axis"],
                    ["Thickness", "0.8 cm", "±0.02 cm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-01-correction-cm-to-mm",
                "category": "correction",
                "description": "Recorded thickness = 0.8 mm vs datasheet thickness = 0.8 cm -> propose 8.0 mm.",
                "component_id": "COMP-001",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "correction_proposed",
                "expected_correction": {"value": 8.0, "unit": "mm"},
                "expected_evidence": {
                    "document_filename": "supplier-COMP-001.pdf",
                    "page_number": 1,
                    "supporting_passage": "Component thickness: 0.8 cm."
                }
            }
        },

        # Case 2: correction mm -> cm
        {
            "case_id": "case-02-correction-mm-to-cm",
            "category": "correction",
            "description": "Recorded width = 25.0 cm vs datasheet width = 25.0 mm -> propose 2.5 cm.",
            "record": {
                "case_id": "case-02-correction-mm-to-cm",
                "record_id": "REC-02",
                "component_id": "COMP-002",
                "revision": "A",
                "attribute_name": "width",
                "recorded_value": 25.0,
                "recorded_unit": "cm",
                "document_reference": {"filename": "supplier-COMP-002.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-002.pdf",
                "component_id": "COMP-002",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-002",
                "primary_passage": "Component width: 25.0 mm.",
                "specs": [
                    ["Length", "50.0 mm", "±0.1 mm", "Longitudinal axis"],
                    ["Width", "25.0 mm", "±0.1 mm", "Transverse axis"],
                    ["Thickness", "5.0 mm", "±0.1 mm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-02-correction-mm-to-cm",
                "category": "correction",
                "description": "Recorded width = 25.0 cm vs datasheet width = 25.0 mm -> propose 2.5 cm.",
                "component_id": "COMP-002",
                "revision": "A",
                "attribute_name": "width",
                "expected_outcome": "correction_proposed",
                "expected_correction": {"value": 2.5, "unit": "cm"},
                "expected_evidence": {
                    "document_filename": "supplier-COMP-002.pdf",
                    "page_number": 1,
                    "supporting_passage": "Component width: 25.0 mm."
                }
            }
        },

        # Case 3: agreement mm
        {
            "case_id": "case-03-agreement-mm",
            "category": "abstention",
            "description": "Recorded thickness = 8.0 mm vs datasheet thickness = 0.8 cm -> values agree, no_change.",
            "record": {
                "case_id": "case-03-agreement-mm",
                "record_id": "REC-03",
                "component_id": "COMP-003",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 8.0,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-003.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-003.pdf",
                "component_id": "COMP-003",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-003",
                "primary_passage": "Component thickness: 0.8 cm.",
                "specs": [
                    ["Length", "25.0 mm", "±0.1 mm", "Longitudinal axis"],
                    ["Width", "15.0 mm", "±0.1 mm", "Transverse axis"],
                    ["Thickness", "0.8 cm", "±0.02 cm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-03-agreement-mm",
                "category": "abstention",
                "description": "Recorded thickness = 8.0 mm vs datasheet thickness = 0.8 cm -> values agree, no_change.",
                "component_id": "COMP-003",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "no_change",
                "expected_correction": None,
                "expected_evidence": {
                    "document_filename": "supplier-COMP-003.pdf",
                    "page_number": 1,
                    "supporting_passage": "Component thickness: 0.8 cm."
                }
            }
        },

        # Case 4: agreement cm
        {
            "case_id": "case-04-agreement-cm",
            "category": "abstention",
            "description": "Recorded width = 2.5 cm vs datasheet width = 25.0 mm -> values agree, no_change.",
            "record": {
                "case_id": "case-04-agreement-cm",
                "record_id": "REC-04",
                "component_id": "COMP-004",
                "revision": "A",
                "attribute_name": "width",
                "recorded_value": 2.5,
                "recorded_unit": "cm",
                "document_reference": {"filename": "supplier-COMP-004.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-004.pdf",
                "component_id": "COMP-004",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-004",
                "primary_passage": "Component width: 25.0 mm.",
                "specs": [
                    ["Length", "50.0 mm", "±0.1 mm", "Longitudinal axis"],
                    ["Width", "25.0 mm", "±0.1 mm", "Transverse axis"],
                    ["Thickness", "5.0 mm", "±0.1 mm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-04-agreement-cm",
                "category": "abstention",
                "description": "Recorded width = 2.5 cm vs datasheet width = 25.0 mm -> values agree, no_change.",
                "component_id": "COMP-004",
                "revision": "A",
                "attribute_name": "width",
                "expected_outcome": "no_change",
                "expected_correction": None,
                "expected_evidence": {
                    "document_filename": "supplier-COMP-004.pdf",
                    "page_number": 1,
                    "supporting_passage": "Component width: 25.0 mm."
                }
            }
        },

        # Case 5: unknown component
        {
            "case_id": "case-05-unknown-component",
            "category": "abstention",
            "description": "Record references COMP-999 not present in document corpus -> insufficient_evidence.",
            "record": {
                "case_id": "case-05-unknown-component",
                "record_id": "REC-05",
                "component_id": "COMP-999",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-005.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-005.pdf",
                "component_id": "COMP-005",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-005",
                "primary_passage": "Component thickness: 0.8 cm.",
                "specs": [
                    ["Thickness", "0.8 cm", "±0.02 cm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-05-unknown-component",
                "category": "abstention",
                "description": "Record references COMP-999 not present in document corpus -> insufficient_evidence.",
                "component_id": "COMP-999",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "insufficient_evidence",
                "expected_correction": None,
                "expected_evidence": None
            }
        },

        # Case 6: incorrect revision
        {
            "case_id": "case-06-incorrect-revision",
            "category": "abstention",
            "description": "Record asks for Rev B, but document is Rev A -> insufficient_evidence.",
            "record": {
                "case_id": "case-06-incorrect-revision",
                "record_id": "REC-06",
                "component_id": "COMP-006",
                "revision": "B",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-006.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-006.pdf",
                "component_id": "COMP-006",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-006",
                "primary_passage": "Component thickness: 0.8 cm.",
                "specs": [
                    ["Thickness", "0.8 cm", "±0.02 cm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-06-incorrect-revision",
                "category": "abstention",
                "description": "Record asks for Rev B, but document is Rev A -> insufficient_evidence.",
                "component_id": "COMP-006",
                "revision": "B",
                "attribute_name": "thickness",
                "expected_outcome": "insufficient_evidence",
                "expected_correction": None,
                "expected_evidence": None
            }
        },

        # Case 7: missing measurement
        {
            "case_id": "case-07-missing-measurement",
            "category": "abstention",
            "description": "Record investigates 'weight', which is missing from document -> insufficient_evidence.",
            "record": {
                "case_id": "case-07-missing-measurement",
                "record_id": "REC-07",
                "component_id": "COMP-007",
                "revision": "A",
                "attribute_name": "weight",
                "recorded_value": 10.0,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-007.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-007.pdf",
                "component_id": "COMP-007",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-007",
                "primary_passage": "Component thickness: 0.8 cm.",
                "specs": [
                    ["Length", "25.0 mm", "±0.1 mm", "Longitudinal axis"],
                    ["Width", "15.0 mm", "±0.1 mm", "Transverse axis"],
                    ["Thickness", "0.8 cm", "±0.02 cm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-07-missing-measurement",
                "category": "abstention",
                "description": "Record investigates 'weight', which is missing from document -> insufficient_evidence.",
                "component_id": "COMP-007",
                "revision": "A",
                "attribute_name": "weight",
                "expected_outcome": "insufficient_evidence",
                "expected_correction": None,
                "expected_evidence": None
            }
        },

        # Case 8: conflicting evidence
        {
            "case_id": "case-08-conflicting-evidence",
            "category": "abstention",
            "description": "Document contains conflicting measurements (0.8 cm vs 1.2 cm) -> ambiguous_evidence.",
            "record": {
                "case_id": "case-08-conflicting-evidence",
                "record_id": "REC-08",
                "component_id": "COMP-008",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-008.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-008.pdf",
                "component_id": "COMP-008",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-008",
                "primary_passage": "Component thickness: 0.8 cm.",
                "secondary_passage": "Variant Component thickness: 1.2 cm.",
                "specs": [
                    ["Thickness (Standard)", "0.8 cm", "±0.02 cm", "Standard package"],
                    ["Thickness (Variant)", "1.2 cm", "±0.02 cm", "Heavy-duty package"]
                ]
            },
            "expected": {
                "case_id": "case-08-conflicting-evidence",
                "category": "abstention",
                "description": "Document contains conflicting measurements (0.8 cm vs 1.2 cm) -> ambiguous_evidence.",
                "component_id": "COMP-008",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "ambiguous_evidence",
                "expected_correction": None,
                "expected_evidence": None
            }
        },

        # Case 9: unsupported unit in evidence
        {
            "case_id": "case-09-unsupported-unit",
            "category": "abstention",
            "description": "Document specifies thickness in unsupported unit 'in' (0.8 in) -> needs_review.",
            "record": {
                "case_id": "case-09-unsupported-unit",
                "record_id": "REC-09",
                "component_id": "COMP-009",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-009.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-009.pdf",
                "component_id": "COMP-009",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-009",
                "primary_passage": "Component thickness: 0.8 in.",
                "specs": [
                    ["Thickness", "0.8 in", "±0.02 in", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-09-unsupported-unit",
                "category": "abstention",
                "description": "Document specifies thickness in unsupported unit 'in' (0.8 in) -> needs_review.",
                "component_id": "COMP-009",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "needs_review",
                "expected_correction": None,
                "expected_evidence": {
                    "document_filename": "supplier-COMP-009.pdf",
                    "page_number": 1,
                    "supporting_passage": "Component thickness: 0.8 in."
                }
            }
        },

        # Case 10: malformed measurement
        {
            "case_id": "case-10-malformed-measurement",
            "category": "abstention",
            "description": "Record value 'INVALID_NUM' is not numeric -> needs_review.",
            "record": {
                "case_id": "case-10-malformed-measurement",
                "record_id": "REC-10",
                "component_id": "COMP-010",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": "INVALID_NUM",
                "recorded_unit": "mm",
                "document_reference": {"filename": "supplier-COMP-010.pdf"}
            },
            "doc": {
                "filename": "supplier-COMP-010.pdf",
                "component_id": "COMP-010",
                "revision": "A",
                "document_id": "DOC-SUP-COMP-010",
                "primary_passage": "Component thickness: 0.8 cm.",
                "specs": [
                    ["Thickness", "0.8 cm", "±0.02 cm", "Substrate thickness"]
                ]
            },
            "expected": {
                "case_id": "case-10-malformed-measurement",
                "category": "abstention",
                "description": "Record value 'INVALID_NUM' is not numeric -> needs_review.",
                "component_id": "COMP-010",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "needs_review",
                "expected_correction": None,
                "expected_evidence": None
            }
        }
    ]

    print(f"Generating {len(case_specs)} evaluation cases...")

    for spec in case_specs:
        cid = spec["case_id"]
        c_dir = cases_dir / cid
        doc_dir = c_dir / "documents"
        ext_dir = c_dir / "extracted"

        c_dir.mkdir(parents=True, exist_ok=True)
        doc_dir.mkdir(parents=True, exist_ok=True)
        ext_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write record.json
        record_path = c_dir / "record.json"
        with open(record_path, "w", encoding="utf-8") as f:
            json.dump(spec["record"], f, indent=2)

        # 2. Build PDF in documents/
        doc_info = spec["doc"]
        pdf_path = doc_dir / doc_info["filename"]
        build_synthetic_pdf(
            pdf_path,
            component_id=doc_info["component_id"],
            revision=doc_info["revision"],
            document_id=doc_info["document_id"],
            primary_passage=doc_info["primary_passage"],
            specs=doc_info["specs"],
            secondary_passage=doc_info.get("secondary_passage")
        )

        # 3. Extract text into extracted/
        extracted_data = extract_pdf(pdf_path)
        extracted_json_path = ext_dir / f"{pdf_path.stem}.json"
        with open(extracted_json_path, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)

        # 4. Write expected JSON explicitly
        exp_path = expected_dir / f"{cid}.json"
        with open(exp_path, "w", encoding="utf-8") as f:
            json.dump(spec["expected"], f, indent=2)

        print(f"  ✓ Created {cid} ({spec['category']})")

    print("\nAll 10 evaluation cases generated successfully.")


def main():
    repo_root = Path(__file__).resolve().parent.parent
    generate_all_cases(repo_root)


if __name__ == "__main__":
    main()
