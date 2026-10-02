#!/usr/bin/env python3
"""LangChain Runnable orchestration for Engineering Data Copilot investigations.

Step 23 implementation:
- Composes the verified investigation workflow using named, composable LangChain Runnables:
  1. validate_record: validates recorded value, decimal validity, and supported units.
  2. retrieve_eligible_evidence: executes pluggable retrieval (baseline or pgvector), wraps
     evidence as LangChain Document representations with complete provenance, and tracks
     retrieval status separately.
  3. branch_on_retrieval_outcome: short-circuits on insufficient/ambiguous evidence or retrieval
     error to skip measurement extraction.
  4. extract_measurement: executes the measurement extractor (deterministic or Gemini adapter)
     exactly once on eligible passages.
  5. validate_and_align_source_quote: applies whitespace-aware quote alignment, attribute
     verification, and value/unit grounding checks. Rejects invalid extractions without proposing
     corrections.
  6. perform_decimal_conversion_and_comparison: performs deterministic Decimal conversion and
     arithmetic comparison.
  7. produce_investigation_response: formats the final investigation response matching the
     contract schema.
- Reuses shared domain functions from scripts.investigate_record without duplicating business logic.
- Preserves citations, page coordinates, and exact business outcomes across all 16 cases.
- Disables external tracing by default (no LangSmith credentials required).
- Records local named-stage timings and invocation counts.
"""

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

# Ensure external LangChain/LangSmith tracing is strictly disabled by default
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

# Add repo root to path
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extractors import (
    BaseMeasurementExtractor,
    DeterministicMeasurementExtractor,
    GeminiMeasurementExtractor,
    get_extractor,
)
from scripts.investigate_record import (
    evaluate_and_compare_measurements,
    evaluate_retrieval_outcome,
    init_base_response,
    make_extractor_metadata,
    validate_extracted_quote_and_guardrails,
    validate_record_inputs,
)
from scripts.retrieve_evidence import retrieve_evidence

# Lazy import check for langchain_core
try:
    from langchain_core.callbacks import BaseCallbackHandler
    from langchain_core.documents import Document
    from langchain_core.runnables import (
        Runnable,
        RunnableLambda,
        RunnableSequence,
    )
    LANGCHAIN_CORE_AVAILABLE = True
except ImportError:
    LANGCHAIN_CORE_AVAILABLE = False
    Document = Any  # type: ignore
    Runnable = Any  # type: ignore


class InvestigationWorkflowState(TypedDict, total=False):
    """Typed workflow state passing through the LangChain Runnable pipeline."""
    # Inputs
    raw_record: Dict[str, Any]
    extracted_dir: Optional[Path]
    extractor_inst: Any
    retriever: Any
    corpus_id: Optional[str]
    retriever_kwargs: Optional[Dict[str, Any]]

    # Base response & record fields
    base_response: Dict[str, Any]
    current_record: Dict[str, Any]
    attribute_name: str
    raw_rec_val: Any
    raw_rec_unit: Any

    # Validation
    is_valid_record: bool
    record_val_dec: Optional[Decimal]
    record_unit_clean: Optional[str]

    # Retrieval
    retrieval_res: Dict[str, Any]
    retrieval_status: str
    evidence_documents: List[Any]  # List[Document]
    primary_document: Optional[Any]  # Optional[Document]

    # Branching
    should_skip_extraction: bool
    passage: Optional[str]
    evidence_dict: Optional[Dict[str, Any]]

    # Extraction
    extractor_res: Any
    extractor_meta: Dict[str, Any]
    should_skip_guardrails: bool

    # Guardrails
    guardrails_passed: bool
    evidence_measurement: Optional[Dict[str, Any]]
    ev_val_dec: Optional[Decimal]
    ev_unit_clean: Optional[str]

    # Response & Telemetry
    early_exit_response: Optional[Dict[str, Any]]
    conversion_response: Optional[Dict[str, Any]]
    final_result: Dict[str, Any]
    telemetry: Dict[str, Any]


def make_stage(name: str, fn: Callable[[Dict[str, Any]], Dict[str, Any]]) -> Any:
    """Wrap a workflow step function as a named LangChain RunnableLambda with local timing and counts."""
    if not LANGCHAIN_CORE_AVAILABLE:
        raise ImportError(
            "langchain-core is not installed. Install requirements-orchestration.txt "
            "to use LangChain workflow orchestration."
        )

    def stage_executor(state: Dict[str, Any]) -> Dict[str, Any]:
        telemetry = state.setdefault("telemetry", {"stage_metrics": {}, "invocation_counts": {}})
        invocations = telemetry["invocation_counts"].get(name, 0) + 1
        telemetry["invocation_counts"][name] = invocations

        t0 = time.perf_counter()
        try:
            return fn(state)
        finally:
            elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
            telemetry["stage_metrics"][name] = {
                "duration_ms": elapsed_ms,
                "invocations": invocations,
            }

    return RunnableLambda(stage_executor, name=name)


# ---------------------------------------------------------------------------
# Named Stage 1: validate_record
# ---------------------------------------------------------------------------
def stage_validate_record(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate engineering record recorded_value, numeric parseability, and supported unit."""
    record = state["raw_record"]
    base_response = state["base_response"]
    extractor_inst = state.get("extractor_inst")

    is_valid, record_val_dec, record_unit_clean, validation_err = validate_record_inputs(
        record, base_response, extractor_inst=extractor_inst
    )
    if not is_valid:
        state["is_valid_record"] = False
        state["early_exit_response"] = validation_err
    else:
        state["is_valid_record"] = True
        state["record_val_dec"] = record_val_dec
        state["record_unit_clean"] = record_unit_clean

    return state


# ---------------------------------------------------------------------------
# Named Stage 2: retrieve_eligible_evidence
# ---------------------------------------------------------------------------
def stage_retrieve_eligible_evidence(state: Dict[str, Any]) -> Dict[str, Any]:
    """Retrieve evidence from baseline filesystem or pgvector, creating Document representation."""
    if state.get("early_exit_response"):
        return state

    record = state["raw_record"]
    extracted_dir = state.get("extracted_dir")
    retriever = state.get("retriever", "baseline")
    corpus_id = state.get("corpus_id")
    retriever_kwargs = state.get("retriever_kwargs") or {}

    retrieval_res = retrieve_evidence(
        record,
        extracted_dir=extracted_dir,
        retriever=retriever,
        corpus_id=corpus_id,
        **retriever_kwargs,
    )

    retrieval_status = retrieval_res.get("status") or retrieval_res.get("retrieval_status")
    state["retrieval_res"] = retrieval_res
    state["retrieval_status"] = retrieval_status

    evidence_dict = retrieval_res.get("evidence")
    passage = retrieval_res.get("evidence_passage") or (evidence_dict.get("supporting_passage") if evidence_dict else None)

    # Represent evidence as LangChain Document where passage exists
    # Preserves filename, page, offsets, corpus identity, and authoritative metadata
    if passage and evidence_dict:
        doc = Document(
            page_content=passage,
            metadata={
                "document_filename": evidence_dict.get("document_filename"),
                "page_number": evidence_dict.get("page_number"),
                "start_char": evidence_dict.get("start_char"),
                "end_char": evidence_dict.get("end_char"),
                "token_count": evidence_dict.get("token_count"),
                "content_sha256": evidence_dict.get("content_sha256"),
                "component_id": evidence_dict.get("component_id") or record.get("component_id") or record.get("part_number"),
                "revision": evidence_dict.get("revision") or record.get("revision"),
                "document_id": evidence_dict.get("document_id"),
                "corpus_id": evidence_dict.get("corpus_id") or corpus_id or "supplier-corpus",
                "context_type": retrieval_res.get("context_type"),
                "similarity_score": evidence_dict.get("similarity_score"),
                "distance": evidence_dict.get("distance"),
            },
        )
        state["evidence_documents"] = [doc]
        state["primary_document"] = doc
    else:
        state["evidence_documents"] = []
        state["primary_document"] = None

    return state


# ---------------------------------------------------------------------------
# Named Stage 3: branch_on_retrieval_outcome
# ---------------------------------------------------------------------------
def stage_branch_on_retrieval_outcome(state: Dict[str, Any]) -> Dict[str, Any]:
    """Branch on retrieval outcome: early abstention (insufficient/ambiguous/error) skips extraction."""
    if state.get("early_exit_response"):
        state["should_skip_extraction"] = True
        return state

    retrieval_res = state["retrieval_res"]
    base_response = state["base_response"]
    extractor_inst = state.get("extractor_inst")

    is_eligible, passage, evidence_dict, retrieval_exit = evaluate_retrieval_outcome(
        retrieval_res, base_response, extractor_inst=extractor_inst
    )

    if not is_eligible:
        state["should_skip_extraction"] = True
        state["early_exit_response"] = retrieval_exit
    else:
        state["should_skip_extraction"] = False
        state["passage"] = passage
        state["evidence_dict"] = evidence_dict

    return state


# ---------------------------------------------------------------------------
# Named Stage 4: extract_measurement
# ---------------------------------------------------------------------------
def stage_extract_measurement(state: Dict[str, Any]) -> Dict[str, Any]:
    """Extract measurement attribute using selected extractor (invoked only once on eligible evidence)."""
    telemetry = state.setdefault("telemetry", {})
    telemetry.setdefault("extractor_invocations", 0)

    if state.get("early_exit_response") or state.get("should_skip_extraction"):
        return state

    # Increment actual extractor model/regex invocation count
    telemetry["extractor_invocations"] += 1

    extractor_inst = state["extractor_inst"]
    passage = state["passage"]
    attribute_name = state["attribute_name"]

    extractor_res = extractor_inst.extract_measurement(passage, attribute_name)
    extractor_meta = make_extractor_metadata(res=extractor_res, extractor_inst=extractor_inst)

    state["extractor_res"] = extractor_res
    state["extractor_meta"] = extractor_meta

    # Check for early extractor abstentions or errors before quote alignment
    if extractor_res.status != "found":
        # Handle non-found statuses via shared guardrail validator
        _, _, _, _, _, failure_exit = validate_extracted_quote_and_guardrails(
            extractor_res=extractor_res,
            passage=passage,
            attribute_name=attribute_name,
            evidence_dict=state.get("evidence_dict"),
            base_response=state["base_response"],
            extractor_meta=extractor_meta,
        )
        state["early_exit_response"] = failure_exit
        state["should_skip_guardrails"] = True
    else:
        state["should_skip_guardrails"] = False

    return state


# ---------------------------------------------------------------------------
# Named Stage 5: validate_and_align_source_quote
# ---------------------------------------------------------------------------
def stage_validate_and_align_source_quote(state: Dict[str, Any]) -> Dict[str, Any]:
    """Validate quote grounding (whitespace alignment), attribute alignment, and unit presence."""
    if state.get("early_exit_response") or state.get("should_skip_guardrails"):
        return state

    extractor_res = state["extractor_res"]
    passage = state["passage"]
    attribute_name = state["attribute_name"]
    evidence_dict = state.get("evidence_dict")
    base_response = state["base_response"]
    extractor_meta = state["extractor_meta"]

    guardrails_passed, updated_evidence_dict, evidence_measurement, ev_val_dec, ev_unit_clean, failure_exit = (
        validate_extracted_quote_and_guardrails(
            extractor_res=extractor_res,
            passage=passage,
            attribute_name=attribute_name,
            evidence_dict=evidence_dict,
            base_response=base_response,
            extractor_meta=extractor_meta,
        )
    )

    if not guardrails_passed:
        state["guardrails_passed"] = False
        state["early_exit_response"] = failure_exit
    else:
        state["guardrails_passed"] = True
        state["evidence_dict"] = updated_evidence_dict
        state["evidence_measurement"] = evidence_measurement
        state["ev_val_dec"] = ev_val_dec
        state["ev_unit_clean"] = ev_unit_clean

    return state


# ---------------------------------------------------------------------------
# Named Stage 6: perform_decimal_conversion_and_comparison
# ---------------------------------------------------------------------------
def stage_perform_decimal_conversion_and_comparison(state: Dict[str, Any]) -> Dict[str, Any]:
    """Perform deterministic Decimal conversion and comparison between record and evidence."""
    if state.get("early_exit_response"):
        return state

    ev_val_dec = state["ev_val_dec"]
    ev_unit_clean = state["ev_unit_clean"]
    record_val_dec = state["record_val_dec"]
    record_unit_clean = state["record_unit_clean"]
    raw_rec_val = state["raw_rec_val"]
    raw_rec_unit = state["raw_rec_unit"]
    base_response = state["base_response"]
    evidence_dict = state.get("evidence_dict")
    extractor_meta = state["extractor_meta"]

    comparison_res = evaluate_and_compare_measurements(
        ev_val_dec=ev_val_dec,
        ev_unit_clean=ev_unit_clean,
        record_val_dec=record_val_dec,
        record_unit_clean=record_unit_clean,
        raw_rec_val=raw_rec_val,
        raw_rec_unit=raw_rec_unit,
        base_response=base_response,
        evidence_dict=evidence_dict,
        extractor_meta=extractor_meta,
    )
    state["conversion_response"] = comparison_res
    return state


# ---------------------------------------------------------------------------
# Named Stage 7: produce_investigation_response
# ---------------------------------------------------------------------------
def stage_produce_investigation_response(state: Dict[str, Any]) -> Dict[str, Any]:
    """Assemble final structured investigation response matching contract schema."""
    final_res = state.get("early_exit_response") or state.get("conversion_response")
    if final_res is None:
        final_res = {
            **state.get("base_response", {}),
            "status": "needs_review",
            "outcome": "needs_review",
            "evidence_measurement": None,
            "proposed_correction": None,
            "evidence": None,
            "extractor": make_extractor_metadata(
                extractor_inst=state.get("extractor_inst"),
                not_invoked_reason="Pipeline produced no final response.",
            ),
            "explanation": "Investigation workflow produced no response.",
        }

    state["final_result"] = final_res
    return final_res


def create_investigation_workflow() -> Any:
    """Create the composed LangChain Runnable sequence for the investigation workflow."""
    if not LANGCHAIN_CORE_AVAILABLE:
        raise ImportError(
            "langchain-core is not installed. Install requirements-orchestration.txt to use LangChain workflow orchestration."
        )

    pipeline = (
        make_stage("validate_record", stage_validate_record)
        | make_stage("retrieve_eligible_evidence", stage_retrieve_eligible_evidence)
        | make_stage("branch_on_retrieval_outcome", stage_branch_on_retrieval_outcome)
        | make_stage("extract_measurement", stage_extract_measurement)
        | make_stage("validate_and_align_source_quote", stage_validate_and_align_source_quote)
        | make_stage("perform_decimal_conversion_and_comparison", stage_perform_decimal_conversion_and_comparison)
        | make_stage("produce_investigation_response", stage_produce_investigation_response)
    )
    return pipeline


def investigate_record_langchain(
    record_path: Union[Path, str, Dict[str, Any]],
    extracted_dir: Optional[Path] = None,
    extractor: Union[str, BaseMeasurementExtractor] = "deterministic",
    retriever: Union[str, Any] = "baseline",
    corpus_id: Optional[str] = None,
    gemini_api_key: Optional[str] = None,
    gemini_model: Optional[str] = None,
    retriever_kwargs: Optional[Dict[str, Any]] = None,
    return_telemetry: bool = False,
) -> Union[Dict[str, Any], Tuple[Dict[str, Any], Dict[str, Any]]]:
    """Execute record investigation using the LangChain Runnable orchestration pipeline.
    
    Preserves existing business decisions, citation grounding, and output schema.
    """
    if not LANGCHAIN_CORE_AVAILABLE:
        raise ImportError(
            "langchain-core is not installed. Install requirements-orchestration.txt (pip install -r requirements-orchestration.txt)."
        )

    repo_root = Path(__file__).resolve().parent.parent
    if extracted_dir is None:
        extracted_dir = repo_root / "data" / "extracted"
    else:
        extracted_dir = Path(extracted_dir)

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

    # 2. Resolve extractor instance
    if isinstance(extractor, str):
        if extractor.lower() in ("gemini", "google-genai"):
            extractor_inst = get_extractor(
                "gemini",
                api_key=gemini_api_key,
                model=gemini_model,
            )
        else:
            extractor_inst = get_extractor("deterministic")
    else:
        extractor_inst = extractor

    # 3. Construct initial workflow state
    state: Dict[str, Any] = {
        "raw_record": record,
        "extracted_dir": extracted_dir,
        "extractor_inst": extractor_inst,
        "retriever": retriever,
        "corpus_id": corpus_id,
        "retriever_kwargs": retriever_kwargs or {},
        "base_response": base_response,
        "current_record": current_record,
        "attribute_name": base_response["attribute_name"],
        "raw_rec_val": current_record["value"],
        "raw_rec_unit": current_record["unit"],
        "telemetry": {
            "stage_metrics": {},
            "invocation_counts": {},
        },
    }

    # 4. Invoke composed workflow
    workflow = create_investigation_workflow()
    result = workflow.invoke(state)

    if return_telemetry:
        return result, state.get("telemetry", {})
    return result
