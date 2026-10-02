#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore")

"""
Investigate engineering records against supplier evidence to propose unit-mismatch corrections.

Step 8 implementation:
- Connects record input -> evidence retrieval -> measurement extraction -> unit conversion -> comparison -> correction proposal.
- Supports pluggable measurement extractors:
  * DeterministicMeasurementExtractor (default baseline using regex)
  * GeminiMeasurementExtractor (optional adapter using google-genai SDK)
- Validates model extractions using strict post-extraction guardrails:
  * Verbatim quote grounding against cited evidence passage
  * Measurement attribute alignment
  * Value and unit presence inside cited quote
  * Unit support verification (only mm and cm)
- Enforces deterministic Decimal arithmetic for all unit conversions; model is never asked for math.
- Collects execution metadata: provider, model, latency, and token usage.
- Returns structured JSON distinguishing:
  * correction_proposed: supported values differ
  * no_change: values already agree after conversion
  * insufficient_evidence / ambiguous_evidence: retrieval or extraction cannot support a decision
  * needs_review: unsupported units, unparseable measurements, or ungrounded model extractions
- Abstention outcomes contain no proposed correction.
- Preserves original record and supplier documents without modification.
- Never reads evaluation/expected/ or project documentation from runtime code.
"""

import argparse
import json
import os
import re
import sys
import time
import warnings
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union

# Suppress known environment deprecation warnings from google-auth and urllib3
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

# Import Step 5 retrieval function and Step 8 extractors
sys.path.insert(0, str(Path(__file__).resolve().parent))
from retrieve_evidence import retrieve_evidence
from extractors import (
    BaseMeasurementExtractor,
    DeterministicMeasurementExtractor,
    GeminiMeasurementExtractor,
    get_extractor,
    load_dotenv,
    SUPPORTED_UNITS
)


def parse_numeric_measurement(text: str, attribute_name: str) -> Tuple[Optional[Decimal], Optional[str], Optional[str]]:
    """Legacy helper function preserving backwards-compatibility.
    
    Delegates to DeterministicMeasurementExtractor.
    """
    extractor = DeterministicMeasurementExtractor()
    res = extractor.extract_measurement(text, attribute_name)
    if res.status == "found":
        return res.value, res.unit, None
    return None, None, res.error_message or "Could not extract measurement."


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


def align_quote_to_passage(quote: str, passage: str) -> Tuple[Optional[str], str, Optional[str]]:
    """Align model-extracted quote to cited evidence passage.
    
    Step 14 whitespace-aware quote alignment rules:
    1. Preserve strict literal matching as the first option.
    2. If that fails, allow only whitespace differences between the quote and source text.
       Maintains exact index mapping back to original source text.
    3. Accept only a uniquely located, contiguous source span.
    4. Return that original verbatim span as the citation, preserving filename and page.
    5. Retain model quote separately for audit.
    6. Never normalize numbers, units, punctuation, or other characters.
    7. Never use fuzzy similarity or join disconnected excerpts.
    8. Missing or ambiguous matches cause rejection (returning None span).

    Returns:
        (verbatim_span, alignment_type, error_message)
        alignment_type is one of: "literal", "whitespace_aligned", "missing", "ambiguous"
    """
    if not quote or not quote.strip():
        return None, "missing", "Empty or missing supporting quote."
    if not passage or not passage.strip():
        return None, "missing", "Empty or missing evidence passage."

    raw_quote = quote.strip()

    # 1. Strict literal matching (first option)
    exact_count = passage.count(raw_quote)
    if exact_count == 1:
        return raw_quote, "literal", None
    elif exact_count > 1:
        return None, "ambiguous", f"Ambiguous quote grounding: quote appears {exact_count} times literally in evidence passage."

    # 2. Whitespace-aware quote alignment (fallback for non-literal whitespace differences)
    quote_tokens = [m.group(0) for m in re.finditer(r'\S+', raw_quote)]
    if not quote_tokens:
        return None, "missing", "No non-whitespace tokens in quote."

    passage_tokens = [(m.group(0), m.start(), m.end()) for m in re.finditer(r'\S+', passage)]
    k = len(quote_tokens)
    if len(passage_tokens) < k:
        return None, "missing", f"Ungrounded extraction: supporting quote '{raw_quote}' was not found in cited evidence passage."

    match_starts = []
    for i in range(len(passage_tokens) - k + 1):
        if [p[0] for p in passage_tokens[i : i + k]] == quote_tokens:
            match_starts.append(i)

    if len(match_starts) == 0:
        return None, "missing", f"Ungrounded extraction: supporting quote '{raw_quote}' was not found in cited evidence passage."
    elif len(match_starts) > 1:
        return None, "ambiguous", f"Ambiguous quote grounding: supporting quote matches {len(match_starts)} distinct spans in cited evidence passage."

    start_idx = match_starts[0]
    span_start = passage_tokens[start_idx][1]
    span_end = passage_tokens[start_idx + k - 1][2]
    verbatim_span = passage[span_start:span_end]

    return verbatim_span, "whitespace_aligned", None


def init_base_response(record: Dict[str, Any]) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Initialize structured base response and current record dictionary."""
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
    return base_response, current_record


def make_extractor_metadata(
    res: Any = None,
    extractor_inst: Any = None,
    not_invoked_reason: Optional[str] = None
) -> Dict[str, Any]:
    """Construct structured telemetry and metadata for the measurement extractor."""
    is_gemini = isinstance(extractor_inst, GeminiMeasurementExtractor)
    default_provider = "google-genai" if is_gemini else "deterministic"
    default_model = getattr(extractor_inst, "model", None) if is_gemini else None

    if res is not None:
        return {
            "provider": res.provider,
            "model": res.model,
            "mode": "deterministic" if res.provider == "deterministic" else "model",
            "is_fallback": res.is_fallback,
            "call_duration_ms": res.call_duration_ms,
            "token_usage": res.token_usage,
            "token_usage_reason": res.token_usage_reason,
            "status": getattr(res, "status", None),
            "error_type": getattr(res, "error_type", None)
        }
    return {
        "provider": default_provider,
        "model": default_model,
        "mode": "model" if is_gemini else "deterministic",
        "is_fallback": False,
        "call_duration_ms": 0.0,
        "token_usage": None,
        "token_usage_reason": not_invoked_reason or "Extractor was not invoked.",
        "status": "not_invoked",
        "error_type": None
    }


def validate_record_inputs(
    record: Dict[str, Any],
    base_response: Dict[str, Any],
    extractor_inst: Any = None
) -> Tuple[bool, Optional[Decimal], Optional[str], Optional[Dict[str, Any]]]:
    """Validate engineering record recorded_value and recorded_unit.
    
    Returns:
        (is_valid, record_val_dec, record_unit_clean, error_response)
    """
    raw_rec_val = record.get("recorded_value")
    raw_rec_unit = record.get("recorded_unit")

    if raw_rec_val is None:
        return False, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(extractor_inst=extractor_inst, not_invoked_reason="Record value is missing; extractor not invoked."),
            "explanation": "Engineering record is missing 'recorded_value'."
        }

    try:
        record_val_dec = Decimal(str(raw_rec_val))
    except (InvalidOperation, TypeError):
        return False, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(extractor_inst=extractor_inst, not_invoked_reason="Record value is not numeric; extractor not invoked."),
            "explanation": f"Engineering record contains invalid numeric value: {raw_rec_val}."
        }

    record_unit_clean = str(raw_rec_unit).strip().lower() if raw_rec_unit else ""
    if record_unit_clean not in SUPPORTED_UNITS:
        return False, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(extractor_inst=extractor_inst, not_invoked_reason="Record unit is unsupported; extractor not invoked."),
            "explanation": f"Record unit '{raw_rec_unit}' is unsupported. Only {sorted(SUPPORTED_UNITS)} are supported."
        }

    return True, record_val_dec, record_unit_clean, None


def evaluate_retrieval_outcome(
    retrieval_res: Dict[str, Any],
    base_response: Dict[str, Any],
    extractor_inst: Any = None
) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
    """Inspect evidence retrieval result for errors or early abstentions.
    
    Returns:
        (is_eligible, passage, evidence_dict, exit_response)
    """
    retrieval_status = retrieval_res.get("status") or retrieval_res.get("retrieval_status")
    context_type = retrieval_res.get("context_type")
    retriever_meta = retrieval_res.get("retriever")

    base_response["retrieval_status"] = retrieval_status
    base_response["context_type"] = context_type
    if retriever_meta:
        base_response["retriever"] = retriever_meta

    if retrieval_status == "error":
        return False, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(extractor_inst=extractor_inst, not_invoked_reason=f"Retrieval error: {retrieval_res.get('reason')}"),
            "explanation": retrieval_res.get("reason", "Evidence retrieval failed."),
        }

    if retrieval_status in ("insufficient_evidence", "ambiguous_evidence"):
        return False, None, None, {
            **base_response,
            "status": retrieval_status,
            "outcome": retrieval_status,
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(extractor_inst=extractor_inst, not_invoked_reason=f"Retrieval yielded {retrieval_status}; extractor not invoked."),
            "explanation": retrieval_res.get("reason", f"Retrieval yielded {retrieval_status}.")
        }

    evidence_dict = retrieval_res.get("evidence")
    passage = retrieval_res.get("evidence_passage") or (evidence_dict.get("supporting_passage") if evidence_dict else None)

    if not passage:
        return False, None, None, {
            **base_response,
            "status": "insufficient_evidence",
            "outcome": "insufficient_evidence",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(extractor_inst=extractor_inst, not_invoked_reason="No evidence passage returned by retrieval."),
            "explanation": "No evidence passage was returned by retrieval."
        }

    return True, passage, evidence_dict, None


def validate_extracted_quote_and_guardrails(
    extractor_res: Any,
    passage: str,
    attribute_name: str,
    evidence_dict: Optional[Dict[str, Any]],
    base_response: Dict[str, Any],
    extractor_meta: Dict[str, Any]
) -> Tuple[bool, Optional[Dict[str, Any]], Optional[Dict[str, Any]], Optional[Decimal], Optional[str], Optional[Dict[str, Any]]]:
    """Apply strict post-extraction verification guardrails.
    
    Returns:
        (guardrails_passed, evidence_dict, evidence_measurement, ev_val_dec, ev_unit_clean, exit_response)
    """
    if extractor_res.status == "error":
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": f"Extraction error: {extractor_res.error_message}"
        }

    if extractor_res.status == "insufficient":
        return False, None, None, None, None, {
            **base_response,
            "status": "insufficient_evidence",
            "outcome": "insufficient_evidence",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": extractor_res.error_message or f"Extractor found insufficient evidence for '{attribute_name}' in cited passage."
        }

    if extractor_res.status == "ambiguous":
        return False, None, None, None, None, {
            **base_response,
            "status": "ambiguous_evidence",
            "outcome": "ambiguous_evidence",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": extractor_res.error_message or f"Extractor identified conflicting or ambiguous measurements for '{attribute_name}' in cited passage."
        }

    raw_quote = extractor_res.quote or ""

    # Guardrail 1: Quote grounding check with whitespace-aware alignment
    verbatim_span, align_type, align_err = align_quote_to_passage(raw_quote, passage)
    if not verbatim_span:
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": align_err or f"Ungrounded extraction: supporting quote '{raw_quote}' was not found in cited evidence passage."
        }

    # Update evidence citation with verbatim contiguous span when whitespace alignment is used
    if evidence_dict:
        if align_type == "whitespace_aligned":
            evidence_dict = {
                **evidence_dict,
                "supporting_passage": verbatim_span,
                "model_quote": raw_quote,
                "quote_alignment": "whitespace_aligned"
            }
        else:
            evidence_dict = {
                **evidence_dict,
                "quote_alignment": "literal"
            }

    # Guardrail 2: Attribute name alignment check
    extracted_attr = extractor_res.measurement_name
    if extracted_attr and extracted_attr.strip().lower() != attribute_name.strip().lower():
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": f"Mismatched measurement: expected attribute '{attribute_name}', but extractor returned '{extracted_attr}'."
        }

    # Guardrail 3: Numeric value validation
    ev_val_dec = extractor_res.value
    if ev_val_dec is None:
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": "Extractor did not return a valid numeric value."
        }

    # Guardrail 4: Value and unit grounding within supporting quote and aligned verbatim span
    val_str = str(ev_val_dec)
    unit_str = (extractor_res.unit or "").strip()
    if val_str not in raw_quote and val_str not in verbatim_span:
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": f"Ungrounded extraction: extracted value '{val_str}' does not appear in supporting quote '{raw_quote}'."
        }

    if unit_str.lower() not in raw_quote.lower() and unit_str.lower() not in verbatim_span.lower():
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": f"Ungrounded extraction: extracted unit '{unit_str}' does not appear in supporting quote '{raw_quote}'."
        }

    ev_unit_clean = unit_str.lower()
    evidence_measurement = {
        "value": float(ev_val_dec),
        "unit": ev_unit_clean
    }

    # Guardrail 5: Supported unit check
    if ev_unit_clean not in SUPPORTED_UNITS:
        return False, None, None, None, None, {
            **base_response,
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": evidence_measurement,
            "proposed_correction": None,
            "evidence": evidence_dict,
            "extractor": extractor_meta,
            "explanation": f"Evidence unit '{ev_unit_clean}' is unsupported. Only {sorted(SUPPORTED_UNITS)} are supported."
        }

    return True, evidence_dict, evidence_measurement, ev_val_dec, ev_unit_clean, None


def evaluate_and_compare_measurements(
    ev_val_dec: Decimal,
    ev_unit_clean: str,
    record_val_dec: Decimal,
    record_unit_clean: str,
    raw_rec_val: Any,
    raw_rec_unit: Any,
    base_response: Dict[str, Any],
    evidence_dict: Optional[Dict[str, Any]],
    extractor_meta: Dict[str, Any]
) -> Dict[str, Any]:
    """Perform deterministic Decimal conversion and comparison between record and evidence."""
    evidence_measurement = {
        "value": float(ev_val_dec),
        "unit": ev_unit_clean
    }

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
            "extractor": extractor_meta,
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
            "extractor": extractor_meta,
            "explanation": (
                f"Evidence states {ev_val_dec} {ev_unit_clean} ({calc_str}), which agrees with "
                f"the recorded value {raw_rec_val} {raw_rec_unit}. No change required."
            )
        }

    # Values differ -> propose correction
    proposed_val_float = float(converted_val_dec)
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
        "extractor": extractor_meta,
        "explanation": (
            f"Supplier document specifies {ev_val_dec} {ev_unit_clean}, which converts via deterministic arithmetic "
            f"to {converted_val_dec} {record_unit_clean} ({calc_str}). Recorded value is {raw_rec_val} {raw_rec_unit}. "
            f"Proposing correction to {proposed_val_float} {record_unit_clean}."
        )
    }


def investigate_record(
    record_path: Union[Path, str, Dict[str, Any]],
    extracted_dir: Optional[Path] = None,
    extractor: Union[str, BaseMeasurementExtractor] = "deterministic",
    retriever: Union[str, Any] = "baseline",
    corpus_id: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    gemini_model: Optional[str] = None,
    retriever_kwargs: Optional[Dict[str, Any]] = None,
    orchestration: str = "direct",
) -> Dict[str, Any]:
    """Investigate an engineering record for measurement-unit mismatches against supplier evidence.
    
    Args:
        record_path: Path to the engineering record JSON file or an in-memory record dict.
        extracted_dir: Path to directory of extracted document JSONs (default: data/extracted).
        extractor: Extractor type ('deterministic' or 'gemini') or a BaseMeasurementExtractor instance.
        retriever: Retriever type ('baseline' or 'pgvector') or a BaseRetriever instance.
        corpus_id: Optional corpus identifier for vector retrieval (default: supplier-corpus).
        gemini_api_key: Optional Gemini API key override (otherwise uses GEMINI_API_KEY env var).
        gemini_model: Optional Gemini model name override (otherwise uses GEMINI_MODEL env var).
        retriever_kwargs: Optional kwargs forwarded to retriever instance.
        orchestration: Execution engine ('direct' for zero-dependency baseline, 'langchain' for Runnable pipeline, 'langgraph' for StateGraph).
    """
    if str(orchestration).strip().lower() == "langchain":
        # Lazy import of LangChain orchestration engine
        from scripts.investigate_chain import investigate_record_langchain
        return investigate_record_langchain(
            record_path=record_path,
            extracted_dir=extracted_dir,
            extractor=extractor,
            retriever=retriever,
            corpus_id=corpus_id,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            retriever_kwargs=retriever_kwargs,
        )

    if str(orchestration).strip().lower() == "langgraph":
        # Lazy import of LangGraph orchestration engine
        from scripts.investigate_graph import investigate_record_langgraph
        return investigate_record_langgraph(
            record_path=record_path,
            extracted_dir=extracted_dir,
            extractor=extractor,
            retriever=retriever,
            corpus_id=corpus_id,
            gemini_api_key=gemini_api_key,
            gemini_model=gemini_model,
            retriever_kwargs=retriever_kwargs,
        )

    # Direct execution path using shared domain functions
    repo_root = Path(__file__).resolve().parent.parent
    if extracted_dir is None:
        extracted_dir = repo_root / "data" / "extracted"

    if isinstance(record_path, dict):
        record = record_path
    else:
        rec_path_obj = Path(record_path)
        if not rec_path_obj.exists():
            raise FileNotFoundError(f"Record file not found: {record_path}")
        with open(rec_path_obj, "r", encoding="utf-8") as f:
            record = json.load(f)

    # 1. Initialize base response
    base_response, current_record = init_base_response(record)
    attribute_name = base_response["attribute_name"]
    raw_rec_val = current_record["value"]
    raw_rec_unit = current_record["unit"]

    # 2. Resolve extractor instance
    if isinstance(extractor, str):
        if extractor.lower() in ("gemini", "google-genai"):
            extractor_inst = get_extractor(
                "gemini",
                api_key=gemini_api_key,
                model=gemini_model
            )
        else:
            extractor_inst = get_extractor("deterministic")
    else:
        extractor_inst = extractor

    # 3. Validate record inputs
    is_valid, record_val_dec, record_unit_clean, validation_err = validate_record_inputs(
        record, base_response, extractor_inst=extractor_inst
    )
    if not is_valid:
        return validation_err  # type: ignore

    # 4. Run evidence retrieval directly as a Python function (baseline or pgvector)
    retrieval_res = retrieve_evidence(
        record,
        extracted_dir=extracted_dir,
        retriever=retriever,
        corpus_id=corpus_id,
        **(retriever_kwargs or {}),
    )

    # 5. Evaluate retrieval outcome
    is_eligible, passage, evidence_dict, retrieval_exit = evaluate_retrieval_outcome(
        retrieval_res, base_response, extractor_inst=extractor_inst
    )
    if not is_eligible:
        return retrieval_exit  # type: ignore

    # 6. Extract measurement using selected extractor
    extractor_res = extractor_inst.extract_measurement(passage, attribute_name)
    extractor_meta = make_extractor_metadata(res=extractor_res, extractor_inst=extractor_inst)

    # 7. Apply strict post-extraction verification guardrails
    guardrails_passed, evidence_dict, evidence_measurement, ev_val_dec, ev_unit_clean, guardrail_exit = (
        validate_extracted_quote_and_guardrails(
            extractor_res=extractor_res,
            passage=passage,  # type: ignore
            attribute_name=attribute_name,
            evidence_dict=evidence_dict,
            base_response=base_response,
            extractor_meta=extractor_meta,
        )
    )
    if not guardrails_passed:
        return guardrail_exit  # type: ignore

    # 8. Convert measurement and compare values using deterministic Decimal arithmetic
    return evaluate_and_compare_measurements(
        ev_val_dec=ev_val_dec,  # type: ignore
        ev_unit_clean=ev_unit_clean,  # type: ignore
        record_val_dec=record_val_dec,  # type: ignore
        record_unit_clean=record_unit_clean,  # type: ignore
        raw_rec_val=raw_rec_val,
        raw_rec_unit=raw_rec_unit,
        base_response=base_response,
        evidence_dict=evidence_dict,
        extractor_meta=extractor_meta,
    )


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
        "--retriever",
        choices=["baseline", "pgvector"],
        default="baseline",
        help="Evidence retriever to use: 'baseline' (default) or 'pgvector'",
    )
    parser.add_argument(
        "--corpus-id",
        type=str,
        default=None,
        help="Optional corpus identifier for vector retrieval (default: supplier-corpus)",
    )
    parser.add_argument(
        "--extractor",
        choices=["deterministic", "gemini"],
        default="deterministic",
        help="Measurement extractor to use: 'deterministic' (default) or 'gemini'",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=None,
        help="Gemini model name (default: GEMINI_MODEL env var or gemini-2.5-flash)",
    )
    parser.add_argument(
        "--orchestration",
        choices=["direct", "langchain", "langgraph"],
        default="direct",
        help="Workflow orchestration execution path: 'direct' (default), 'langchain', or 'langgraph'",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Optional path to write output JSON result",
    )
    args = parser.parse_args()

    try:
        result = investigate_record(
            args.record_path,
            extracted_dir=args.extracted_dir,
            extractor=args.extractor,
            retriever=args.retriever,
            corpus_id=args.corpus_id,
            gemini_model=args.model,
            orchestration=args.orchestration,
        )

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
