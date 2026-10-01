#!/usr/bin/env python3
"""
Generate the 6 challenge synthetic evaluation cases for Step 11.

Creates:
- evaluation/cases/challenge-<id>/record.json
- evaluation/cases/challenge-<id>/documents/supplier-<id>.pdf
- evaluation/cases/challenge-<id>/extracted/supplier-<id>.json
- evaluation/expected/challenge-<id>.json (explicitly authored expectations)

Isolation:
Each challenge case has an isolated documents/ and extracted/ corpus directory.
Expected outcomes are stored separately under evaluation/expected/.
"""

import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

sys.path.insert(0, str(Path(__file__).resolve().parent))
from extract_documents import extract_pdf


def build_challenge_pdf(
    output_path: Path,
    component_id: str,
    revision: str,
    document_id: str,
    layout_type: str,
    content_config: Dict[str, Any]
):
    """Generate a single-page synthetic supplier datasheet PDF tailored to challenge requirements."""
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

    # 1. Red Synthetic Banner
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

    # 2. Header
    elements.append(Paragraph("Apex Microelectronics Corp. — Supplier Datasheet", title_style))
    elements.append(Paragraph("Technical Product Specification & Interface Guidelines", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=8))

    # 3. Metadata Table
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

    # 4. Section 1: Product Overview
    elements.append(Paragraph("1. Product Overview", heading2_style))
    overview_text = (
        f"This document serves as the authoritative supplier technical specification for revision {revision} "
        f"of component {component_id}. All physical dimensions herein supersede preliminary notes."
    )
    elements.append(Paragraph(overview_text, body_style))
    elements.append(Spacer(1, 6))

    # 5. Section 2: Physical Dimensions & Mechanical Parameters
    elements.append(Paragraph("2. Physical Dimensions & Mechanical Parameters", heading2_style))
    intro_dim = f"Mechanical parameters and specifications for component ID {component_id} (25°C, 50% RH):"
    elements.append(Paragraph(intro_dim, body_style))
    elements.append(Spacer(1, 4))

    # Tailored layout per challenge requirement
    if layout_type == "complete_sentence":
        # Case 1: Complete sentence
        sentence = content_config["sentence"]
        elements.append(Paragraph(sentence, callout_style))
        elements.append(Spacer(1, 6))

        # Secondary standard specs table
        table_data = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Nominal Value</b>", body_style), Paragraph("<b>Tolerance</b>", body_style), Paragraph("<b>Notes</b>", body_style)],
            [Paragraph("Operating Temp", body_style), Paragraph("-40°C to +85°C", body_style), Paragraph("±2°C", body_style), Paragraph("Standard commercial range", body_style)],
            [Paragraph("Mounting Style", body_style), Paragraph("Surface Mount", body_style), Paragraph("N/A", body_style), Paragraph("Solder reflow compliant", body_style)]
        ]
        t = Table(table_data, colWidths=[120, 100, 90, 194])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elif layout_type == "table_separated_columns":
        # Case 2: Table with separate parameter, value, and unit columns
        t_intro = "Authoritative dimensional values are detailed in the parameter table below:"
        elements.append(Paragraph(t_intro, body_style))
        elements.append(Spacer(1, 4))

        table_data = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Nominal Value</b>", body_style), Paragraph("<b>Unit</b>", body_style), Paragraph("<b>Tolerance</b>", body_style)],
            [Paragraph("Thickness", body_style), Paragraph("15.0", body_style), Paragraph("mm", body_style), Paragraph("±0.1 mm", body_style)],
            [Paragraph("Width", body_style), Paragraph("25.0", body_style), Paragraph("mm", body_style), Paragraph("±0.2 mm", body_style)],
            [Paragraph("Length", body_style), Paragraph("50.0", body_style), Paragraph("mm", body_style), Paragraph("±0.2 mm", body_style)],
        ]
        t = Table(table_data, colWidths=[120, 100, 90, 194])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elif layout_type == "split_lines":
        # Case 3: Label and measurement split across lines
        split_text = "Component Thickness:<br/>2.4 mm"
        elements.append(Paragraph(split_text, callout_style))
        elements.append(Spacer(1, 6))

        table_data = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Nominal Value</b>", body_style), Paragraph("<b>Tolerance</b>", body_style), Paragraph("<b>Notes</b>", body_style)],
            [Paragraph("Lead Count", body_style), Paragraph("8", body_style), Paragraph("N/A", body_style), Paragraph("Gold plated leads", body_style)],
            [Paragraph("Package Material", body_style), Paragraph("Ceramic", body_style), Paragraph("N/A", body_style), Paragraph("Hermetic seal", body_style)]
        ]
        t = Table(table_data, colWidths=[120, 100, 90, 194])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elif layout_type == "distracting_measurements":
        # Case 4: Thickness alongside distracting width and length measurements
        distracting_text = content_config["passage"]
        elements.append(Paragraph(distracting_text, callout_style))
        elements.append(Spacer(1, 6))

        table_data = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Nominal Value</b>", body_style), Paragraph("<b>Tolerance</b>", body_style), Paragraph("<b>Notes</b>", body_style)],
            [Paragraph("Mass", body_style), Paragraph("1.8 g", body_style), Paragraph("±0.05 g", body_style), Paragraph("Dry component mass", body_style)],
            [Paragraph("Thermal Resistance", body_style), Paragraph("12.5 °C/W", body_style), Paragraph("±1 °C/W", body_style), Paragraph("Junction to ambient", body_style)]
        ]
        t = Table(table_data, colWidths=[120, 100, 90, 194])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elif layout_type == "incorrect_revision":
        # Case 5: Correct component but only incorrect revision B in document
        elements.append(Paragraph(content_config["passage"], callout_style))
        elements.append(Spacer(1, 6))

        table_data = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Nominal Value</b>", body_style), Paragraph("<b>Tolerance</b>", body_style), Paragraph("<b>Notes</b>", body_style)],
            [Paragraph("Supply Voltage", body_style), Paragraph("3.3 V", body_style), Paragraph("±0.1 V", body_style), Paragraph("Standard logic rail", body_style)]
        ]
        t = Table(table_data, colWidths=[120, 100, 90, 194])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elif layout_type == "conflicting_statements":
        # Case 6: Two conflicting thickness statements
        elements.append(Paragraph(content_config["passage_1"], callout_style))
        elements.append(Paragraph(content_config["passage_2"], callout_style))
        elements.append(Spacer(1, 6))

        table_data = [
            [Paragraph("<b>Parameter</b>", body_style), Paragraph("<b>Nominal Value</b>", body_style), Paragraph("<b>Tolerance</b>", body_style), Paragraph("<b>Notes</b>", body_style)],
            [Paragraph("Clock Frequency", body_style), Paragraph("100 MHz", body_style), Paragraph("±1 MHz", body_style), Paragraph("Internal PLL", body_style)]
        ]
        t = Table(table_data, colWidths=[120, 100, 90, 194])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
            ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
            ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
            ('LEFTPADDING', (0, 0), (-1, -1), 6),
            ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ]))
        elements.append(t)

    elements.append(Spacer(1, 8))

    # 6. Section 3: Synthetic Demonstration Notice
    elements.append(Paragraph("3. Synthetic Demonstration Notice", heading2_style))
    notice_text = (
        "This datasheet is entirely synthetic demonstration data created for testing and verifying the "
        "Engineering Data Investigation Copilot benchmark suite."
    )
    elements.append(Paragraph(notice_text, body_style))
    elements.append(Spacer(1, 10))

    # 7. Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=2, spaceAfter=6))
    elements.append(Paragraph(
        f"Page 1 of 1 | Document ID: {document_id} | Revision: {revision} | Synthetic Test Dataset",
        footer_style
    ))

    doc.build(elements)


def generate_challenge_suite(repo_root: Path):
    cases_dir = repo_root / "evaluation" / "cases"
    expected_dir = repo_root / "evaluation" / "expected"

    cases_dir.mkdir(parents=True, exist_ok=True)
    expected_dir.mkdir(parents=True, exist_ok=True)

    challenge_specs = [
        # 1. Thickness stated in a complete sentence
        {
            "case_id": "challenge-01-complete-sentence",
            "category": "challenge_sentence",
            "description": "Thickness stated in a complete sentence: 1.2 cm vs recorded 1.2 mm -> propose 12.0 mm.",
            "component_id": "COMP-C01",
            "revision": "A",
            "document_id": "DOC-SUP-COMP-C01",
            "pdf_name": "supplier-COMP-C01.pdf",
            "layout_type": "complete_sentence",
            "content_config": {
                "sentence": "Under standard ambient conditions, the nominal thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots."
            },
            "record": {
                "case_id": "challenge-01-complete-sentence",
                "record_id": "REC-CHALLENGE-001",
                "component_id": "COMP-C01",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 1.2,
                "recorded_unit": "mm",
                "document_reference": {
                    "filename": "supplier-COMP-C01.pdf"
                }
            },
            "expected": {
                "case_id": "challenge-01-complete-sentence",
                "category": "challenge_sentence",
                "description": "Thickness stated in a complete sentence: 1.2 cm vs recorded 1.2 mm -> propose 12.0 mm.",
                "component_id": "COMP-C01",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "correction_proposed",
                "expected_correction": {
                    "value": 12.0,
                    "unit": "mm"
                },
                "expected_evidence": {
                    "document_filename": "supplier-COMP-C01.pdf",
                    "page_number": 1,
                    "supporting_passage": "Under standard ambient conditions, the nominal thickness of component COMP-C01 is manufactured to 1.2 cm across all production lots."
                },
                "failure_stage": "retrieval",
                "limitation_note": "Line-based candidate passage regex expects an immediate delimiter (':', '=', or 'is') followed directly by the number; descriptive sentences containing interstitial phrases (e.g. 'is manufactured to 1.2 cm') fail candidate extraction."
            }
        },

        # 2. Thickness represented in a table with separate value/unit columns
        {
            "case_id": "challenge-02-table-value-unit-columns",
            "category": "challenge_table",
            "description": "Thickness represented in table with separate parameter, value, and unit columns: 15.0 mm vs recorded 15.0 cm -> propose 1.5 cm.",
            "component_id": "COMP-C02",
            "revision": "A",
            "document_id": "DOC-SUP-COMP-C02",
            "pdf_name": "supplier-COMP-C02.pdf",
            "layout_type": "table_separated_columns",
            "content_config": {},
            "record": {
                "case_id": "challenge-02-table-value-unit-columns",
                "record_id": "REC-CHALLENGE-002",
                "component_id": "COMP-C02",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 15.0,
                "recorded_unit": "cm",
                "document_reference": {
                    "filename": "supplier-COMP-C02.pdf"
                }
            },
            "expected": {
                "case_id": "challenge-02-table-value-unit-columns",
                "category": "challenge_table",
                "description": "Thickness represented in table with separate parameter, value, and unit columns: 15.0 mm vs recorded 15.0 cm -> propose 1.5 cm.",
                "component_id": "COMP-C02",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "correction_proposed",
                "expected_correction": {
                    "value": 1.5,
                    "unit": "cm"
                },
                "expected_evidence": {
                    "document_filename": "supplier-COMP-C02.pdf",
                    "page_number": 1,
                    "supporting_passage": "Thickness\n15.0\nmm"
                },
                "failure_stage": "retrieval",
                "limitation_note": "Multi-column table cells are extracted by pypdf as individual separate lines ('Thickness\\n15.0\\nmm'). Line-by-line scanning cannot correlate the attribute name with values and units located in subsequent table lines."
            }
        },

        # 3. Thickness label and measurement split across lines
        {
            "case_id": "challenge-03-split-lines-label-measurement",
            "category": "challenge_split_lines",
            "description": "Thickness label and measurement split across lines: 2.4 mm vs recorded 2.4 cm -> propose 0.24 cm.",
            "component_id": "COMP-C03",
            "revision": "A",
            "document_id": "DOC-SUP-COMP-C03",
            "pdf_name": "supplier-COMP-C03.pdf",
            "layout_type": "split_lines",
            "content_config": {},
            "record": {
                "case_id": "challenge-03-split-lines-label-measurement",
                "record_id": "REC-CHALLENGE-003",
                "component_id": "COMP-C03",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 2.4,
                "recorded_unit": "cm",
                "document_reference": {
                    "filename": "supplier-COMP-C03.pdf"
                }
            },
            "expected": {
                "case_id": "challenge-03-split-lines-label-measurement",
                "category": "challenge_split_lines",
                "description": "Thickness label and measurement split across lines: 2.4 mm vs recorded 2.4 cm -> propose 0.24 cm.",
                "component_id": "COMP-C03",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "correction_proposed",
                "expected_correction": {
                    "value": 0.24,
                    "unit": "cm"
                },
                "expected_evidence": {
                    "document_filename": "supplier-COMP-C03.pdf",
                    "page_number": 1,
                    "supporting_passage": "Component Thickness:\n2.4 mm"
                },
                "failure_stage": "retrieval",
                "limitation_note": "Retrieval splits extracted page text strictly on newlines and processes each line in isolation. When an attribute label and its numeric measurement are wrapped across a newline, neither line individually matches candidate extraction."
            }
        },

        # 4. Thickness alongside distracting width and length measurements
        {
            "case_id": "challenge-04-distracting-measurements",
            "category": "challenge_distracting",
            "description": "Thickness listed alongside length and width: thickness is 6.0 mm vs recorded 0.6 cm -> values agree, no_change.",
            "component_id": "COMP-C04",
            "revision": "A",
            "document_id": "DOC-SUP-COMP-C04",
            "pdf_name": "supplier-COMP-C04.pdf",
            "layout_type": "distracting_measurements",
            "content_config": {
                "passage": "Package dimensions (length, width, thickness): 60.0 mm x 40.0 mm x 6.0 mm."
            },
            "record": {
                "case_id": "challenge-04-distracting-measurements",
                "record_id": "REC-CHALLENGE-004",
                "component_id": "COMP-C04",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.6,
                "recorded_unit": "cm",
                "document_reference": {
                    "filename": "supplier-COMP-C04.pdf"
                }
            },
            "expected": {
                "case_id": "challenge-04-distracting-measurements",
                "category": "challenge_distracting",
                "description": "Thickness listed alongside length and width: thickness is 6.0 mm vs recorded 0.6 cm -> values agree, no_change.",
                "component_id": "COMP-C04",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "no_change",
                "expected_correction": None,
                "expected_evidence": {
                    "document_filename": "supplier-COMP-C04.pdf",
                    "page_number": 1,
                    "supporting_passage": "Package dimensions (length, width, thickness): 60.0 mm x 40.0 mm x 6.0 mm."
                },
                "failure_stage": "retrieval",
                "limitation_note": "Candidate passage regex matches the nearest numeric token following 'thickness' (which matches the adjacent length '60.0 mm' after the closing parenthesis). As a result, the pipeline extracts the wrong dimension (60.0 mm instead of 6.0 mm) and proposes an incorrect correction (6.0 cm) instead of no_change."
            }
        },

        # 5. Correct component but only an incorrect document revision
        {
            "case_id": "challenge-05-incorrect-revision",
            "category": "challenge_revision",
            "description": "Datasheet has revision B while record specifies revision A -> return insufficient_evidence.",
            "component_id": "COMP-C05",
            "revision": "B",  # Document has Rev B!
            "document_id": "DOC-SUP-COMP-C05-B",
            "pdf_name": "supplier-COMP-C05-B.pdf",
            "layout_type": "incorrect_revision",
            "content_config": {
                "passage": "Component thickness: 0.8 cm."
            },
            "record": {
                "case_id": "challenge-05-incorrect-revision",
                "record_id": "REC-CHALLENGE-005",
                "component_id": "COMP-C05",
                "revision": "A",  # Record requires Rev A!
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {
                    "filename": "supplier-COMP-C05-B.pdf"
                }
            },
            "expected": {
                "case_id": "challenge-05-incorrect-revision",
                "category": "challenge_revision",
                "description": "Datasheet has revision B while record specifies revision A -> return insufficient_evidence.",
                "component_id": "COMP-C05",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "insufficient_evidence",
                "expected_correction": None,
                "expected_evidence": None,
                "failure_stage": None,
                "limitation_note": "Expected behavior: Revision guardrail correctly identifies revision mismatch and safely abstains with insufficient_evidence."
            }
        },

        # 6. Two conflicting thickness statements for the same component and revision
        {
            "case_id": "challenge-06-conflicting-statements",
            "category": "challenge_conflict",
            "description": "Two conflicting thickness statements (0.8 cm and 1.2 cm) in the same document -> return ambiguous_evidence.",
            "component_id": "COMP-C06",
            "revision": "A",
            "document_id": "DOC-SUP-COMP-C06",
            "pdf_name": "supplier-COMP-C06.pdf",
            "layout_type": "conflicting_statements",
            "content_config": {
                "passage_1": "Component thickness: 0.8 cm.",
                "passage_2": "Alternative packaging thickness: 1.2 cm."
            },
            "record": {
                "case_id": "challenge-06-conflicting-statements",
                "record_id": "REC-CHALLENGE-006",
                "component_id": "COMP-C06",
                "revision": "A",
                "attribute_name": "thickness",
                "recorded_value": 0.8,
                "recorded_unit": "mm",
                "document_reference": {
                    "filename": "supplier-COMP-C06.pdf"
                }
            },
            "expected": {
                "case_id": "challenge-06-conflicting-statements",
                "category": "challenge_conflict",
                "description": "Two conflicting thickness statements (0.8 cm and 1.2 cm) in the same document -> return ambiguous_evidence.",
                "component_id": "COMP-C06",
                "revision": "A",
                "attribute_name": "thickness",
                "expected_outcome": "ambiguous_evidence",
                "expected_correction": None,
                "expected_evidence": None,
                "failure_stage": None,
                "limitation_note": "Expected behavior: Ambiguity resolution guardrail detects multiple distinct thickness measurements and safely abstains with ambiguous_evidence."
            }
        }
    ]

    print("Generating 6 challenge synthetic evaluation cases...")

    for spec in challenge_specs:
        cid = spec["case_id"]
        c_dir = cases_dir / cid
        docs_dir = c_dir / "documents"
        ext_dir = c_dir / "extracted"

        c_dir.mkdir(parents=True, exist_ok=True)
        docs_dir.mkdir(parents=True, exist_ok=True)
        ext_dir.mkdir(parents=True, exist_ok=True)

        # 1. Write record.json
        rec_path = c_dir / "record.json"
        with open(rec_path, "w", encoding="utf-8") as f:
            json.dump(spec["record"], f, indent=2)

        # 2. Build PDF
        pdf_path = docs_dir / spec["pdf_name"]
        build_challenge_pdf(
            output_path=pdf_path,
            component_id=spec["component_id"],
            revision=spec["revision"],
            document_id=spec["document_id"],
            layout_type=spec["layout_type"],
            content_config=spec["content_config"]
        )

        # 3. Extract PDF into isolated extracted/
        extracted_data = extract_pdf(pdf_path)
        extracted_json_path = ext_dir / f"{pdf_path.stem}.json"
        with open(extracted_json_path, "w", encoding="utf-8") as f:
            json.dump(extracted_data, f, indent=2, ensure_ascii=False)

        # 4. Write expected answer separately under evaluation/expected/
        exp_path = expected_dir / f"{cid}.json"
        with open(exp_path, "w", encoding="utf-8") as f:
            json.dump(spec["expected"], f, indent=2)

        print(f"  [✓] Created challenge case: {cid}")

    print("\nAll 6 challenge evaluation cases generated successfully.")


if __name__ == "__main__":
    repo_root = Path(__file__).resolve().parent.parent
    generate_challenge_suite(repo_root)
