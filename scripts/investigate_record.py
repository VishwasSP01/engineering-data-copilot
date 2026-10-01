#!/usr/bin/env python3
"""
Investigate engineering records against supplier evidence to propose unit-mismatch corrections.

Step 6 implementation:
- Connects record input -> evidence retrieval -> unit conversion -> comparison -> correction proposal.
- Reuses Step 5 retrieval logic as a direct Python function import (no shell invocation).
- Extracts unambiguous measurement values and units (mm and cm) from retrieved evidence passage.
- Converts units using deterministic Decimal arithmetic (1 cm = 10 mm).
- Returns structured JSON distinguishing:
  * correction_proposed: supported values differ
  * no_change: values already agree after conversion
  * insufficient_evidence / ambiguous_evidence: retrieval cannot support a decision
  * needs_review: unsupported units or unparseable measurements
- Abstention outcomes contain no proposed correction.
- Preserves original record and supplier documents without modification.
- Never reads evaluation/expected/ or project documentation from runtime code.
"""

import argparse
import json
import re
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

# Import Step 5 retrieval function directly
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieve_evidence import retrieve_evidence


SUPPORTED_UNITS = {"mm", "cm"}


def parse_numeric_measurement(text: str, attribute_name: str) -> Tuple[Optional[Decimal], Optional[str], Optional[str]]:
    """Extract nominal numeric value and unit for the attribute from text.
    
    Returns:
        (value_decimal, unit_str, error_message)
    """
    if not text:
        return None, None, "Empty text provided."

    # Pattern 1: attribute followed by number and unit
    pattern_fwd = rf'\b{re.escape(attribute_name)}\b[^\n.!?]*?(?:[:=]|\bis\b)?\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)'
    m = re.search(pattern_fwd, text, re.IGNORECASE)

    # Pattern 2: number and unit followed by attribute
    if not m:
        pattern_rev = rf'(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)\s+(?:[A-Za-z0-9_-]+\s+)*{re.escape(attribute_name)}'
        m = re.search(pattern_rev, text, re.IGNORECASE)

    # Pattern 3: direct measurement on a standalone line
    if not m:
        pattern_line = r'^\s*(?:[A-Za-z0-9_-]+\s+)*(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)'
        m = re.search(pattern_line, text, re.IGNORECASE)

    if not m:
        return None, None, f"Could not find a numeric measurement for '{attribute_name}' in evidence passage."

    raw_val = m.group(1)
    raw_unit = m.group(2).lower()

    try:
        val_dec = Decimal(raw_val)
    except InvalidOperation:
        return None, None, f"Could not parse numeric value '{raw_val}' as Decimal."

    return val_dec, raw_unit, None


def convert_measurement(
    val: Decimal,
    from_unit: str,
    to_unit: str
) -> Tuple[Decimal, Decimal, str]:
    """Convert measurement between mm and cm using deterministic Decimal arithmetic.
    
    Returns:
        (converted_value, multiplier, calculation_formula)
    """
    from_u = from_unit.lower()
    to_u = to_unit.lower()

    if from_u not in SUPPORTED_UNITS or to_u not in SUPPORTED_UNITS:
        raise ValueError(f"Conversion between '{from_unit}' and '{to_unit}' is unsupported. Only 'mm' and 'cm' are supported.")

    if from_u == to_u:
        multiplier = Decimal("1")
        converted = val
        calc = f"{val} {from_u} = {converted} {to_u}"
        return converted, multiplier, calc

    if from_u == "cm" and to_u == "mm":
        multiplier = Decimal("10")
        converted = val * multiplier
        calc = f"{val} cm * 10 mm/cm = {converted} mm"
        return converted, multiplier, calc

    if from_u == "mm" and to_u == "cm":
        multiplier = Decimal("0.1")
        converted = val * multiplier
        calc = f"{val} mm * 0.1 cm/mm = {converted} cm"
        return converted, multiplier, calc

    raise ValueError(f"Unhandled unit conversion from '{from_unit}' to '{to_unit}'.")


def investigate_record(record_path: Path, extracted_dir: Optional[Path] = None) -> Dict[str, Any]:
    """Investigate an engineering record for measurement-unit mismatches against supplier evidence."""
    repo_root = Path(__file__).resolve().parent.parent
    if extracted_dir is None:
        extracted_dir = repo_root / "data" / "extracted"

    if not record_path.exists():
        raise FileNotFoundError(f"Record file not found: {record_path}")

    with open(record_path, "r", encoding="utf-8") as f:
        record = json.load(f)

    case_id = record.get("case_id") or record.get("record_id") or "UNKNOWN-CASE"
    record_id = record.get("record_id") or record.get("case_id") or "UNKNOWN-RECORD"
    component_id = record.get("component_id") or record.get("part_number") or "UNKNOWN-COMP"
    revision = record.get("revision")
    attribute_name = record.get("attribute_name") or record.get("attribute") or record.get("measurement") or "unknown_attribute"

    raw_rec_val = record.get("recorded_value")
    raw_rec_unit = record.get("recorded_unit")

    current_record = {
        "value": raw_rec_val,
        "unit": raw_rec_unit
    }

    base_response = {
        "case_id": case_id,
        "record_id": record_id,
        "component_id": component_id,
        "revision": revision,
        "attribute_name": attribute_name,
        "current_record": current_record,
        "source_record_modified": False
    }

    # Validate record's recorded value
    if raw_rec_val is None:
        return {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "explanation": "Engineering record is missing 'recorded_value'."
        }

    try:
        record_val_dec = Decimal(str(raw_rec_val))
    except (InvalidOperation, TypeError):
        return {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "explanation": f"Engineering record contains invalid numeric value: {raw_rec_val}."
        }

    # Validate record's unit
    record_unit_clean = str(raw_rec_unit).strip().lower() if raw_rec_unit else ""
    if record_unit_clean not in SUPPORTED_UNITS:
        return {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "explanation": f"Record unit '{raw_rec_unit}' is unsupported. Only {sorted(SUPPORTED_UNITS)} are supported."
        }

    # Run Step 5 evidence retrieval directly as a Python function
    retrieval_res = retrieve_evidence(record_path, extracted_dir=extracted_dir)
    retrieval_status = retrieval_res.get("status") or retrieval_res.get("retrieval_status")

    # Handle retrieval abstentions
    if retrieval_status in ("insufficient_evidence", "ambiguous_evidence"):
        return {
            **base_response,
            "status": retrieval_status,
            "outcome": retrieval_status,
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "explanation": retrieval_res.get("reason", f"Retrieval yielded {retrieval_status}.")
        }

    evidence_dict = retrieval_res.get("evidence")
    passage = retrieval_res.get("evidence_passage") or (evidence_dict.get("supporting_passage") if evidence_dict else None)

    if not passage:
        return {
            **base_response,
            "status": "insufficient_evidence",
            "outcome": "insufficient_evidence",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "explanation": "No evidence passage was returned by retrieval."
        }

    # Extract measurement from cited passage
    ev_val_dec, ev_unit_clean, err = parse_numeric_measurement(passage, attribute_name)
    if err or ev_val_dec is None or ev_unit_clean is None:
        return {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "explanation": f"Unable to parse measurement from cited passage: {err}"
        }

    evidence_measurement = {
        "value": float(ev_val_dec),
        "unit": ev_unit_clean
    }

    # Validate evidence unit is supported
    if ev_unit_clean not in SUPPORTED_UNITS:
        return {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": evidence_measurement,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "explanation": f"Evidence unit '{ev_unit_clean}' is unsupported. Only {sorted(SUPPORTED_UNITS)} are supported."
        }

    # Convert evidence measurement into record's unit using Decimal arithmetic
    try:
        converted_val_dec, multiplier_dec, calc_str = convert_measurement(
            ev_val_dec,
            from_unit=ev_unit_clean,
            to_unit=record_unit_clean
        )
    except Exception as exc:
        return {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": evidence_measurement,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "explanation": f"Conversion error: {exc}"
        }

    # Compare converted evidence value with record value exactly
    if record_val_dec == converted_val_dec:
        return {
            **base_response,
            "status": "no_change",
            "outcome": "no_change",
            "evidence_measurement": evidence_measurement,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "explanation": (
                f"Evidence states {ev_val_dec} {ev_unit_clean} ({calc_str}), which agrees with "
                f"the recorded value {raw_rec_val} {raw_rec_unit}. No change required."
            )
        }

    # Values differ -> propose correction
    proposed_val_float = float(converted_val_dec)
    # If the converted decimal is an integer, format cleanly
    if converted_val_dec == converted_val_dec.to_integral():
        proposed_val_float = float(converted_val_dec)

    proposed_correction = {
        "value": proposed_val_float,
        "unit": record_unit_clean,
        "conversion": {
            "supplier_extracted_value": float(ev_val_dec),
            "supplier_extracted_unit": ev_unit_clean,
            "target_unit": record_unit_clean,
            "multiplier": float(multiplier_dec),
            "calculation": calc_str,
            "method": "deterministic_arithmetic"
        }
    }

    return {
        **base_response,
        "status": "correction_proposed",
        "outcome": "correction_proposed",
        "evidence_measurement": evidence_measurement,
        "proposed_correction": proposed_correction,
        "evidence": evidence_dict,
        "explanation": (
            f"Supplier document specifies {ev_val_dec} {ev_unit_clean}, which converts via deterministic arithmetic "
            f"to {converted_val_dec} {record_unit_clean} ({calc_str}). Recorded value is {raw_rec_val} {raw_rec_unit}. "
            f"Proposing correction to {proposed_val_float} {record_unit_clean}."
        )
    }


def main():
    parser = argparse.ArgumentParser(description="Investigate an engineering record and propose evidence-backed unit corrections.")
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
        result = investigate_record(args.record_path, extracted_dir=args.extracted_dir)
        output_str = json.dumps(result, indent=2, ensure_ascii=False)
        print(output_str)

        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(output_str + "\n")

    except Exception as exc:
        print(f"Error during investigation: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
