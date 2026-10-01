# Engineering Data Investigation Copilot — Project Brief

## 1. Problem and Intended User

### Problem
Engineering data records stored in systems such as ERP (Enterprise Resource Planning), PLM (Product Lifecycle Management), and component catalogs frequently suffer from data entry and ingestion errors. A critical and prevalent error class is the **measurement-unit mismatch**—for instance, an engineer or automated ingestion script enters a numerical value directly from a supplier datasheet into a database field expecting a different unit of measure (e.g., recording `0.8` as millimeters when the supplier specified `0.8` centimeters).

Such discrepancies can lead to severe downstream consequences:
- Compromised manufacturing tolerances and assembly fit issues.
- Failed quality audits and regulatory compliance risks.
- Costly scrap, rework, and supply chain delays.

Manual cross-referencing between engineering databases and supplier datasheet PDFs is tedious, slow, and error-prone.

### Intended User
The primary users are:
- **Engineering Data Stewards & Quality Engineers**: Professionals responsible for maintaining data integrity across component libraries and engineering databases.
- **Component & Design Engineers**: Engineers verifying supplier specifications during component selection and qualification.
- **Procurement & Supply Chain Specialists**: Teams cross-referencing supplier part parameters against internal part definitions.

The Copilot acts as an advisory assistant: it automates the discovery and verification of discrepancies, providing evidence-backed proposals while keeping human engineers in the loop.

---

## 2. The Example Investigation

Consider a typical unit-mismatch scenario:

1. **Engineering Record**:
   - Attribute: `thickness`
   - Recorded Value: `0.8`
   - Recorded Unit: `mm` (0.8 millimeters)
   - Supporting Document: `supplier_datasheet_xyz.pdf`

2. **Supplier Datasheet**:
   - Document: `supplier_datasheet_xyz.pdf` (Page 2)
   - Stated Specification: Component thickness is specified as `0.8 cm` (0.8 centimeters).

3. **Investigation & Analysis**:
   - The Copilot inspects the supplier datasheet on Page 2 and extracts the stated dimension (`0.8 cm`).
   - The Copilot recognizes that `0.8 cm` equals `8.0 mm`.
   - The recorded database value of `0.8 mm` is a factor of 10 off, indicating that the numeric value `0.8` was transcribed without unit conversion.

4. **Deterministic Arithmetic Verification**:
   - Conversion calculation: \( 0.8\text{ cm} \times 10\text{ mm/cm} = 8.0\text{ mm} \).
   - The conversion is validated using deterministic arithmetic rather than language model estimation.

5. **Outcome & Proposal**:
   - The Copilot proposes correcting `thickness` from `0.8 mm` to `8.0 mm`.
   - The proposal includes the provenance citation: `supplier_datasheet_xyz.pdf`, Page 2, with the exact extracted passage.
   - The source record remains strictly unchanged; the proposal is presented via CLI for engineer review.

---

## 3. Input and Output Examples in JSON

### Input Format
The first version consumes a single engineering record as a JSON object referencing the target attribute and supporting document.

```json
{
  "record_id": "REC-ENG-2026-0042",
  "part_number": "CMP-RES-0805",
  "attribute_name": "thickness",
  "recorded_value": 0.8,
  "recorded_unit": "mm",
  "document_reference": {
    "filename": "supplier_datasheet_xyz.pdf",
    "filepath": "documents/supplier_datasheet_xyz.pdf"
  }
}
```

### Output Format: Proposed Correction (Success)
When evidence supports a correction, the Copilot outputs a structured proposal with deterministic verification and evidence citation.

```json
{
  "investigation_id": "INV-20261001-001",
  "record_id": "REC-ENG-2026-0042",
  "attribute_name": "thickness",
  "status": "correction_proposed",
  "current_record": {
    "value": 0.8,
    "unit": "mm"
  },
  "proposed_correction": {
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
    "document_filename": "supplier_datasheet_xyz.pdf",
    "page_number": 2,
    "supporting_passage": "Component Dimensions: Overall component thickness is 0.8 cm nominal under standard mounting."
  },
  "source_record_modified": false
}
```

### Output Format: Insufficient Evidence
When the document lacks the attribute, the passage is ambiguous, or no mismatch can be verified, the Copilot returns an `insufficient_evidence` result.

```json
{
  "investigation_id": "INV-20261001-002",
  "record_id": "REC-ENG-2026-0042",
  "attribute_name": "thickness",
  "status": "insufficient_evidence",
  "current_record": {
    "value": 0.8,
    "unit": "mm"
  },
  "proposed_correction": null,
  "evidence": null,
  "reason": "Supporting document 'supplier_datasheet_xyz.pdf' does not contain a thickness specification for part CMP-RES-0805.",
  "source_record_modified": false
}
```

---

## 4. What Counts as a Successful Investigation

An investigation is considered successful if and only if it fulfills all of the following conditions:

1. **Accurate Mismatch Identification**: Correctly determines whether the recorded unit and value conflict with the supplier document.
2. **Strict Evidence Grounding**: The proposed correction is directly supported by evidence citing:
   - The exact document filename.
   - The exact page number.
   - A verbatim supporting passage from the document.
   Hallucinated passages or unverified citations count as complete failures.
3. **Deterministic Arithmetic Verification**: All unit conversions (e.g., `cm` to `mm`, `in` to `mm`, `g` to `kg`) are performed and verified via deterministic code-based calculation, not probabilistic LLM arithmetic.
4. **Non-Destructive Execution**: The original engineering record is left completely intact and unmodified. The tool outputs a proposal, never an unconfirmed database write.
5. **Calibrated Abstention**: When evidence is missing, conflicting, or inconclusive, the system safely returns `"insufficient_evidence"` rather than producing a speculative proposal.

---

## 5. What Happens When Evidence is Missing or Ambiguous

The Copilot follows a strict fail-safe policy:

- **Missing Attribute or Document**:
  - If the supplier document cannot be resolved, or if the document does not mention the target attribute (e.g., thickness), the Copilot outputs `status: "insufficient_evidence"` with a diagnostic explanation specifying what was missing.
- **Ambiguous or Conflicting Values**:
  - If the datasheet lists multiple conflicting thickness values (e.g., across multiple package variants or unstated test conditions without a matching part modifier), the system flags the ambiguity and returns `status: "insufficient_evidence"`.
- **Missing or Indeterminate Units**:
  - If the document provides a numerical value without an explicit unit of measure, or uses non-standard abbreviations that cannot be unambiguously resolved, the system does not guess. It returns `status: "insufficient_evidence"`.
- **No In-Place Modifications**:
  - Under no circumstances does the Copilot guess, fabricate a value, or modify the source record.

---

## 6. Evaluation: Correctness, Evidence Support, Latency, and Model Cost

The system's performance will be measured across four core dimensions:

| Evaluation Dimension | Metric / Criterion | Target / Standard |
|---|---|---|
| **Correctness** | Precision & Recall on detected unit mismatches; accuracy of proposed numeric values. | Zero false positives in proposed corrections; 100% mathematical accuracy via deterministic arithmetic. |
| **Evidence Support** | Citation accuracy (filename match, page match, verbatim passage verification). | 100% of proposals must point to verifiable, unaltered text on the specified page. |
| **Latency** | End-to-end turnaround time per record investigation via CLI. | Consistent and acceptable response time per single-record/single-document query (target < 5–10 seconds). |
| **Model Cost** | Token usage (prompt tokens, completion tokens) and estimated API cost per investigation. | Cost-effective token utilization through targeted extraction and prompt discipline; minimal redundant LLM calls. |

---

## 7. Deferred Features

To maintain clear focus on the first version, the following capabilities are explicitly deferred:

- **Frontend / UI**: Angular or web-based user interface (CLI is used initially).
- **Additional Error Classes**: Typographical transpositions, wrong part number references, tolerance range mismatches, date/revision mismatches, or multi-field discrepancies.
- **Multi-Agent Architectures**: Multi-agent debate, autonomous agent swarms, or complex dynamic routing.
- **Model Training**: Fine-tuning, custom weight training, or domain-specific base model training.
- **Cloud Deployment & Infrastructure**: Cloud-hosted APIs, Kubernetes clusters, distributed message queues, or managed cloud services.
