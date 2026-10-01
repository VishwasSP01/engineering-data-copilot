#!/usr/bin/env python3
"""
Generate reproducible synthetic investigation sample for unit-mismatch-001.

Artifacts produced:
- data/records/unit-mismatch-001.json
- data/documents/supplier-COMP-001.pdf
- evaluation/expected/unit-mismatch-001.json
"""

import json
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle


def generate_record(output_path: Path):
    """Generate the engineering record JSON."""
    record = {
        "case_id": "unit-mismatch-001",
        "record_id": "unit-mismatch-001",
        "component_id": "COMP-001",
        "part_number": "COMP-001",
        "revision": "A",
        "attribute_name": "thickness",
        "recorded_value": 0.8,
        "recorded_unit": "mm",
        "document_reference": {
            "document_id": "DOC-SUP-COMP-001",
            "filename": "supplier-COMP-001.pdf",
            "filepath": "data/documents/supplier-COMP-001.pdf"
        }
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    print(f"Generated record: {output_path}")


def generate_expected(output_path: Path):
    """Generate the expected evaluation output JSON."""
    expected = {
        "case_id": "unit-mismatch-001",
        "record_id": "unit-mismatch-001",
        "component_id": "COMP-001",
        "revision": "A",
        "attribute_name": "thickness",
        "status": "correction_proposed",
        "current_record": {
            "value": 0.8,
            "unit": "mm"
        },
        "expected_correction": {
            "value": 8.0,
            "unit": "mm",
            "conversion": {
                "supplier_extracted_value": 0.8,
                "supplier_extracted_unit": "cm",
                "target_unit": "mm",
                "multiplier": 10.0,
                "calculation": "0.8 cm * 10 mm/cm = 8.0 mm",
                "method": "deterministic_arithmetic"
            }
        },
        "evidence": {
            "document_filename": "supplier-COMP-001.pdf",
            "page_number": 1,
            "supporting_passage": "Component thickness: 0.8 cm."
        },
        "source_record_modified": False
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(expected, f, indent=2)
    print(f"Generated expected evaluation: {output_path}")


def generate_pdf(output_path: Path):
    """Generate the single-page synthetic supplier datasheet PDF."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(output_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=40,
        bottomMargin=40
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=18,
        leading=22,
        textColor=colors.HexColor('#1E293B'),
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#64748B'),
        spaceAfter=12
    )

    banner_style = ParagraphStyle(
        'SyntheticBanner',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#DC2626'),
        alignment=1  # Centered
    )

    heading2_style = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=colors.HexColor('#0F172A'),
        spaceBefore=12,
        spaceAfter=6
    )

    body_style = ParagraphStyle(
        'Body',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor('#334155')
    )

    callout_style = ParagraphStyle(
        'KeyPassage',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=11,
        leading=16,
        textColor=colors.HexColor('#1E3A8A'),
        spaceBefore=6,
        spaceAfter=6
    )

    footer_style = ParagraphStyle(
        'FooterNote',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=8,
        leading=11,
        textColor=colors.HexColor('#94A3B8'),
        alignment=1
    )

    elements = []

    # Synthetic Demonstration Banner
    banner_table = Table(
        [[Paragraph("SYNTHETIC DEMONSTRATION DATA — FOR TESTING AND EVALUATION ONLY", banner_style)]],
        colWidths=[504]
    )
    banner_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEE2E2')),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor('#F87171')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(banner_table)
    elements.append(Spacer(1, 12))

    # Supplier Header
    elements.append(Paragraph("Apex Microelectronics Corp. — Supplier Datasheet", title_style))
    elements.append(Paragraph("Technical Product Specification & Interface Guidelines", subtitle_style))
    elements.append(HRFlowable(width="100%", thickness=1.5, color=colors.HexColor('#CBD5E1'), spaceBefore=2, spaceAfter=12))

    # Document & Component Metadata Table
    metadata_data = [
        [
            Paragraph("<b>Component ID:</b> COMP-001", body_style),
            Paragraph("<b>Revision:</b> A", body_style)
        ],
        [
            Paragraph("<b>Document ID:</b> DOC-SUP-COMP-001", body_style),
            Paragraph("<b>Effective Date:</b> 2026-10-01", body_style)
        ],
        [
            Paragraph("<b>Part Description:</b> Precision Alumina Substrate Carrier", body_style),
            Paragraph("<b>Status:</b> Authoritative Supplier Release", body_style)
        ]
    ]
    meta_table = Table(metadata_data, colWidths=[252, 252])
    meta_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8FAFC')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#E2E8F0')),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ('RIGHTPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements.append(meta_table)
    elements.append(Spacer(1, 10))

    # Section 1: Overview
    elements.append(Paragraph("1. Product Overview", heading2_style))
    overview_text = (
        "The COMP-001 is a high-grade ceramic substrate carrier designed for surface-mount hybrid "
        "circuits. This document serves as the authoritative supplier technical specification for "
        "revision A of component COMP-001. All physical dimensions herein supersede preliminary notes."
    )
    elements.append(Paragraph(overview_text, body_style))
    elements.append(Spacer(1, 10))

    # Section 2: Physical Specifications
    elements.append(Paragraph("2. Physical Dimensions & Mechanical Parameters", heading2_style))
    intro_dim = (
        "Mechanical measurements for component ID COMP-001 under standard test conditions (25°C, 50% RH). "
        "Note the primary dimensional measurements recorded below:"
    )
    elements.append(Paragraph(intro_dim, body_style))
    elements.append(Spacer(1, 6))

    # Exact passage requirement callout
    elements.append(Paragraph("Component thickness: 0.8 cm.", callout_style))
    elements.append(Spacer(1, 6))

    # Specification Table
    specs_data = [
        [
            Paragraph("<b>Parameter</b>", body_style),
            Paragraph("<b>Nominal Value</b>", body_style),
            Paragraph("<b>Tolerance</b>", body_style),
            Paragraph("<b>Notes</b>", body_style)
        ],
        [
            Paragraph("Length", body_style),
            Paragraph("25.0 mm", body_style),
            Paragraph("±0.1 mm", body_style),
            Paragraph("Longitudinal body axis", body_style)
        ],
        [
            Paragraph("Width", body_style),
            Paragraph("15.0 mm", body_style),
            Paragraph("±0.1 mm", body_style),
            Paragraph("Transverse body axis", body_style)
        ],
        [
            Paragraph("Thickness", body_style),
            Paragraph("0.8 cm", body_style),
            Paragraph("±0.02 cm", body_style),
            Paragraph("Overall substrate height", body_style)
        ],
        [
            Paragraph("Substrate Material", body_style),
            Paragraph("96% Al2O3", body_style),
            Paragraph("—", body_style),
            Paragraph("High-purity alumina", body_style)
        ]
    ]
    specs_table = Table(specs_data, colWidths=[120, 100, 90, 194])
    specs_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#E2E8F0')),
        ('BOX', (0, 0), (-1, -1), 0.5, colors.HexColor('#94A3B8')),
        ('INNERGRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
    ]))
    elements.append(specs_table)
    elements.append(Spacer(1, 14))

    # Section 3: Synthetic Data Notice
    elements.append(Paragraph("3. Synthetic Demonstration Notice", heading2_style))
    notice_text = (
        "This datasheet is entirely synthetic demonstration data created for testing and verifying the "
        "Engineering Data Investigation Copilot. It simulates an authoritative supplier document containing "
        "the exact passage \"Component thickness: 0.8 cm.\" to validate automated unit-mismatch detection "
        "and deterministic arithmetic verification against records specifying 0.8 mm."
    )
    elements.append(Paragraph(notice_text, body_style))
    elements.append(Spacer(1, 16))

    # Footer
    elements.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor('#E2E8F0'), spaceBefore=4, spaceAfter=8))
    elements.append(Paragraph(
        "Page 1 of 1 | Document ID: DOC-SUP-COMP-001 | Revision: A | Synthetic Test Dataset",
        footer_style
    ))

    doc.build(elements)
    print(f"Generated PDF: {output_path}")


def main():
    repo_root = Path(__file__).resolve().parent.parent

    record_path = repo_root / "data" / "records" / "unit-mismatch-001.json"
    doc_path = repo_root / "data" / "documents" / "supplier-COMP-001.pdf"
    expected_path = repo_root / "evaluation" / "expected" / "unit-mismatch-001.json"

    print("Generating synthetic sample artifacts...")
    generate_record(record_path)
    generate_pdf(doc_path)
    generate_expected(expected_path)
    print("Sample generation complete.")


if __name__ == "__main__":
    main()
