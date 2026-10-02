#!/usr/bin/env python3
"""Controlled LangGraph StateGraph orchestration for Engineering Data Copilot investigations.

Step 24 implementation:
- Represents the investigation workflow as an explicit, guarded StateGraph:
  validate_record → retrieve_evidence → extract_measurement → validate_evidence → convert_and_compare → finalize
- Explicit conditional branching:
  * Invalid record → finalize
  * Missing/conflicting evidence or retrieval error → finalize
  * Extraction failure/abstention → finalize
  * Failed grounding or measurement validation → finalize
  * Only validated evidence reaches conversion
- Typed LangChain tool interfaces for retrieval, extraction, and conversion.
- Reuses shared domain functions without duplicating business logic.
- Conversion inputs strictly read from validated graph state.
- Finite execution with no retry cycles (max 6 transitions; recursion_limit=10).
- Local observability: records node transitions, node timings, and tool invocation counts.
- External tracing strictly disabled by default (no LangSmith credentials required).
"""

import json
import os
import sys
import time
import warnings
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

warnings.filterwarnings("ignore", category=PendingDeprecationWarning)
warnings.filterwarnings("ignore", message=".*allowed_objects.*")
try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
    warnings.simplefilter("ignore", LangChainPendingDeprecationWarning)
except ImportError:
    pass

# Ensure external LangChain/LangSmith tracing is strictly disabled by default
os.environ.setdefault("LANGCHAIN_TRACING_V2", "false")
os.environ.setdefault("LANGSMITH_TRACING", "false")

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.extractors import (
    BaseMeasurementExtractor,
    DeterministicMeasurementExtractor,
    GeminiMeasurementExtractor,
    ExtractorResult,
    get_extractor,
)
from scripts.investigate_record import (
    convert_measurement,
    evaluate_and_compare_measurements,
    evaluate_retrieval_outcome,
    init_base_response,
    make_extractor_metadata,
    validate_extracted_quote_and_guardrails,
    validate_record_inputs,
)
from scripts.retrieve_evidence import retrieve_evidence

# Lazy import check for LangChain and LangGraph
try:
    from langchain_core.documents import Document
    from langchain_core.tools import BaseTool, tool
    from langgraph.graph import END, START, StateGraph
    from pydantic import BaseModel, ConfigDict, Field
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    Document = Any  # type: ignore
    BaseTool = Any  # type: ignore
    StateGraph = Any  # type: ignore
    START = "__start__"
    END = "__end__"
    BaseModel = object  # type: ignore
    Field = lambda *args, **kwargs: None  # type: ignore
    ConfigDict = lambda *args, **kwargs: None  # type: ignore


# ---------------------------------------------------------------------------
# Typed Tools (Requirement 4)
# ---------------------------------------------------------------------------
if LANGGRAPH_AVAILABLE:
    class RetrievalToolInput(BaseModel):
        """Input schema for EvidenceRetrievalTool."""
        model_config = ConfigDict(arbitrary_types_allowed=True)
        record: Dict[str, Any] = Field(..., description="Engineering record to retrieve evidence for")
        extracted_dir: Optional[str] = Field(None, description="Path to extracted document directory")
        retriever: str = Field("baseline", description="Retriever name: 'baseline' or 'pgvector'")
        corpus_id: Optional[str] = Field(None, description="Optional corpus identifier for vector retrieval")
        retriever_kwargs: Optional[Dict[str, Any]] = Field(default=None, description="Additional retriever kwargs")

    @tool("evidence_retrieval_tool", args_schema=RetrievalToolInput)
    def evidence_retrieval_tool(
        record: Dict[str, Any],
        extracted_dir: Optional[str] = None,
        retriever: str = "baseline",
        corpus_id: Optional[str] = None,
        retriever_kwargs: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Retrieve evidence passage or chunks from extracted document corpus or pgvector."""
        ext_path = Path(extracted_dir) if extracted_dir else None
        return retrieve_evidence(
            record,
            extracted_dir=ext_path,
            retriever=retriever,
            corpus_id=corpus_id,
            **(retriever_kwargs or {}),
        )

    class ExtractionToolInput(BaseModel):
        """Input schema for MeasurementExtractionTool."""
        model_config = ConfigDict(arbitrary_types_allowed=True)
        evidence_passage: str = Field(..., description="Evidence passage text to extract measurement from")
        attribute_name: str = Field(..., description="Target physical attribute name (e.g. thickness)")
        extractor_type: str = Field("deterministic", description="Extractor to use: 'deterministic' or 'gemini'")
        extractor_inst: Optional[Any] = Field(None, description="Pre-instantiated BaseMeasurementExtractor")

    @tool("measurement_extraction_tool", args_schema=ExtractionToolInput)
    def measurement_extraction_tool(
        evidence_passage: str,
        attribute_name: str,
        extractor_type: str = "deterministic",
        extractor_inst: Optional[Any] = None,
    ) -> Any:
        """Extract physical measurement value, unit, and quote using deterministic regex or Gemini adapter."""
        active_inst = extractor_inst if extractor_inst is not None else get_extractor(extractor_type)
        return active_inst.extract_measurement(evidence_passage, attribute_name)

    class ConversionComparisonToolInput(BaseModel):
        """Input schema for MeasurementConversionComparisonTool."""
        model_config = ConfigDict(arbitrary_types_allowed=True)
        evidence_value: str = Field(..., description="Validated numeric evidence value as string (e.g. '0.8')")
        evidence_unit: str = Field(..., description="Validated evidence unit (e.g. 'cm')")
        record_value: str = Field(..., description="Validated numeric record value as string (e.g. '8.0')")
        record_unit: str = Field(..., description="Validated record unit (e.g. 'mm')")

    @tool("measurement_conversion_tool", args_schema=ConversionComparisonToolInput)
    def measurement_conversion_tool(
        evidence_value: str,
        evidence_unit: str,
        record_value: str,
        record_unit: str,
    ) -> Dict[str, Any]:
        """Convert measurement units via deterministic Decimal arithmetic and compare with record value."""
        ev_val = Decimal(evidence_value)
        rec_val = Decimal(record_value)
        converted_val, multiplier, calc_str = convert_measurement(
            ev_val,
            from_unit=evidence_unit,
            to_unit=record_unit,
        )
        agrees = (converted_val == rec_val)
        return {
            "converted_value": converted_val,
            "multiplier": multiplier,
            "calculation": calc_str,
            "agrees": agrees,
        }


# ---------------------------------------------------------------------------
# Typed Investigation State (Requirement 2)
# ---------------------------------------------------------------------------
class InvestigationGraphState(TypedDict, total=False):
    """Typed state for a single engineering record investigation execution."""
    # 1. Inputs & Configuration (per-investigation, isolated)
    record: Dict[str, Any]
    extracted_dir: Optional[Path]
    retriever_name: str
    extractor_name: str
    extractor_inst: Any
    corpus_id: Optional[str]
    retriever_kwargs: Dict[str, Any]

    # 2. Base Identity & Response Fields
    case_id: str
    record_id: str
    component_id: str
    revision: Optional[str]
    attribute_name: str
    current_record: Dict[str, Any]
    base_response: Dict[str, Any]
    raw_rec_val: Any
    raw_rec_unit: Any

    # 3. Node 1: Record Validation State
    is_record_valid: bool
    record_val_dec: Optional[Decimal]
    record_unit_clean: Optional[str]

    # 4. Node 2: Retrieval State & Cited Evidence
    retrieval_status: str
    evidence_documents: List[Any]  # List[Document]
    evidence_passage: Optional[str]
    evidence_dict: Optional[Dict[str, Any]]
    context_type: Optional[str]
    retriever_meta: Optional[Dict[str, Any]]

    # 5. Node 3: Extraction State
    extractor_invoked: bool
    extractor_res: Optional[Any]  # ExtractorResult
    extractor_meta: Optional[Dict[str, Any]]

    # 6. Node 4: Evidence Validation & Guardrail State
    is_evidence_valid: bool
    verbatim_quote_span: Optional[str]
    quote_alignment_type: Optional[str]
    validated_evidence_measurement: Optional[Dict[str, Any]]
    validated_evidence_dict: Optional[Dict[str, Any]]
    validated_ev_val_dec: Optional[Decimal]
    validated_ev_unit_clean: Optional[str]

    # 7. Node 5 & 6: Terminal Outcome & Final Response
    is_terminal: bool
    terminal_reason: Optional[str]
    final_response: Dict[str, Any]

    # 8. Observability: Node transitions, timings, and tool counts
    node_transitions: List[str]
    node_timings: Dict[str, float]
    tool_invocations: Dict[str, int]


# ---------------------------------------------------------------------------
# Graph Nodes
# ---------------------------------------------------------------------------
def node_validate_record(state: InvestigationGraphState) -> Dict[str, Any]:
    """Node 1: Validate recorded value, Decimal parseability, and supported units."""
    t0 = time.perf_counter()
    transitions = list(state.get("node_transitions", []))
    transitions.append("validate_record")
    timings = dict(state.get("node_timings", {}))
    tools = dict(state.get("tool_invocations", {}))

    record = state["record"]
    base_response = state["base_response"]
    extractor_inst = state.get("extractor_inst")

    is_valid, record_val_dec, record_unit_clean, validation_err = validate_record_inputs(
        record, base_response, extractor_inst=extractor_inst
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    timings["validate_record"] = elapsed_ms

    if not is_valid:
        return {
            "node_transitions": transitions,
            "node_timings": timings,
            "tool_invocations": tools,
            "is_record_valid": False,
            "is_terminal": True,
            "terminal_reason": "record_validation_failed",
            "final_response": validation_err,
        }

    return {
        "node_transitions": transitions,
        "node_timings": timings,
        "tool_invocations": tools,
        "is_record_valid": True,
        "record_val_dec": record_val_dec,
        "record_unit_clean": record_unit_clean,
    }


def node_retrieve_evidence(state: InvestigationGraphState) -> Dict[str, Any]:
    """Node 2: Retrieve eligible evidence using typed EvidenceRetrievalTool."""
    t0 = time.perf_counter()
    transitions = list(state.get("node_transitions", []))
    transitions.append("retrieve_evidence")
    timings = dict(state.get("node_timings", {}))
    tools = dict(state.get("tool_invocations", {}))

    # Invoke EvidenceRetrievalTool
    tools["evidence_retrieval_tool"] = tools.get("evidence_retrieval_tool", 0) + 1
    ext_dir_str = str(state["extracted_dir"]) if state.get("extracted_dir") else None

    retrieval_res = evidence_retrieval_tool.invoke({
        "record": state["record"],
        "extracted_dir": ext_dir_str,
        "retriever": state.get("retriever_name", "baseline"),
        "corpus_id": state.get("corpus_id"),
        "retriever_kwargs": state.get("retriever_kwargs") or {},
    })

    retrieval_status = retrieval_res.get("status") or retrieval_res.get("retrieval_status")
    evidence_dict = retrieval_res.get("evidence")
    passage = retrieval_res.get("evidence_passage") or (evidence_dict.get("supporting_passage") if evidence_dict else None)
    context_type = retrieval_res.get("context_type")
    retriever_meta = retrieval_res.get("retriever")

    # Represent evidence as LangChain Document where eligible passage exists
    docs: List[Any] = []
    if passage and evidence_dict:
        rec = state["record"]
        doc = Document(
            page_content=passage,
            metadata={
                "document_filename": evidence_dict.get("document_filename"),
                "page_number": evidence_dict.get("page_number"),
                "start_char": evidence_dict.get("start_char"),
                "end_char": evidence_dict.get("end_char"),
                "token_count": evidence_dict.get("token_count"),
                "content_sha256": evidence_dict.get("content_sha256"),
                "component_id": evidence_dict.get("component_id") or rec.get("component_id") or rec.get("part_number"),
                "revision": evidence_dict.get("revision") or rec.get("revision"),
                "document_id": evidence_dict.get("document_id"),
                "corpus_id": evidence_dict.get("corpus_id") or state.get("corpus_id") or "supplier-corpus",
                "context_type": context_type,
                "similarity_score": evidence_dict.get("similarity_score"),
                "distance": evidence_dict.get("distance"),
            },
        )
        docs.append(doc)

    # Evaluate retrieval outcome
    is_eligible, valid_passage, valid_ev_dict, retrieval_exit = evaluate_retrieval_outcome(
        retrieval_res, state["base_response"], extractor_inst=state.get("extractor_inst")
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    timings["retrieve_evidence"] = elapsed_ms

    if not is_eligible:
        return {
            "node_transitions": transitions,
            "node_timings": timings,
            "tool_invocations": tools,
            "retrieval_status": retrieval_status,
            "context_type": context_type,
            "retriever_meta": retriever_meta,
            "evidence_documents": docs,
            "is_terminal": True,
            "terminal_reason": f"retrieval_{retrieval_status}",
            "final_response": retrieval_exit,
        }

    return {
        "node_transitions": transitions,
        "node_timings": timings,
        "tool_invocations": tools,
        "retrieval_status": retrieval_status,
        "context_type": context_type,
        "retriever_meta": retriever_meta,
        "evidence_documents": docs,
        "evidence_passage": valid_passage,
        "evidence_dict": valid_ev_dict,
        "is_terminal": False,
    }


def node_extract_measurement(state: InvestigationGraphState) -> Dict[str, Any]:
    """Node 3: Extract measurement using typed MeasurementExtractionTool (invoked once on eligible evidence)."""
    t0 = time.perf_counter()
    transitions = list(state.get("node_transitions", []))
    transitions.append("extract_measurement")
    timings = dict(state.get("node_timings", {}))
    tools = dict(state.get("tool_invocations", {}))

    # Invoke MeasurementExtractionTool
    tools["measurement_extraction_tool"] = tools.get("measurement_extraction_tool", 0) + 1
    passage = state["evidence_passage"] or ""
    attribute_name = state["attribute_name"]
    extractor_inst = state.get("extractor_inst")

    extractor_res = measurement_extraction_tool.invoke({
        "evidence_passage": passage,
        "attribute_name": attribute_name,
        "extractor_type": state.get("extractor_name", "deterministic"),
        "extractor_inst": extractor_inst,
    })

    extractor_meta = make_extractor_metadata(res=extractor_res, extractor_inst=extractor_inst)

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    timings["extract_measurement"] = elapsed_ms

    if extractor_res.status != "found":
        # Handle early extractor failure/abstention via shared guardrail validator
        _, _, _, _, _, failure_exit = validate_extracted_quote_and_guardrails(
            extractor_res=extractor_res,
            passage=passage,
            attribute_name=attribute_name,
            evidence_dict=state.get("evidence_dict"),
            base_response=state["base_response"],
            extractor_meta=extractor_meta,
        )
        return {
            "node_transitions": transitions,
            "node_timings": timings,
            "tool_invocations": tools,
            "extractor_invoked": True,
            "extractor_res": extractor_res,
            "extractor_meta": extractor_meta,
            "is_terminal": True,
            "terminal_reason": f"extractor_{extractor_res.status}",
            "final_response": failure_exit,
        }

    return {
        "node_transitions": transitions,
        "node_timings": timings,
        "tool_invocations": tools,
        "extractor_invoked": True,
        "extractor_res": extractor_res,
        "extractor_meta": extractor_meta,
        "is_terminal": False,
    }


def node_validate_evidence(state: InvestigationGraphState) -> Dict[str, Any]:
    """Node 4: Validate quote grounding (whitespace alignment), attribute alignment, and unit presence."""
    t0 = time.perf_counter()
    transitions = list(state.get("node_transitions", []))
    transitions.append("validate_evidence")
    timings = dict(state.get("node_timings", {}))
    tools = dict(state.get("tool_invocations", {}))

    extractor_res = state["extractor_res"]
    passage = state["evidence_passage"] or ""
    attribute_name = state["attribute_name"]
    evidence_dict = state.get("evidence_dict")
    base_response = state["base_response"]
    extractor_meta = state.get("extractor_meta") or {}

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

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    timings["validate_evidence"] = elapsed_ms

    if not guardrails_passed:
        return {
            "node_transitions": transitions,
            "node_timings": timings,
            "tool_invocations": tools,
            "is_evidence_valid": False,
            "is_terminal": True,
            "terminal_reason": "guardrail_validation_failed",
            "final_response": failure_exit,
        }

    return {
        "node_transitions": transitions,
        "node_timings": timings,
        "tool_invocations": tools,
        "is_evidence_valid": True,
        "validated_evidence_dict": updated_evidence_dict,
        "validated_evidence_measurement": evidence_measurement,
        "validated_ev_val_dec": ev_val_dec,
        "validated_ev_unit_clean": ev_unit_clean,
        "is_terminal": False,
    }


def node_convert_and_compare(state: InvestigationGraphState) -> Dict[str, Any]:
    """Node 5: Convert units and compare using typed MeasurementConversionComparisonTool."""
    t0 = time.perf_counter()
    transitions = list(state.get("node_transitions", []))
    transitions.append("convert_and_compare")
    timings = dict(state.get("node_timings", {}))
    tools = dict(state.get("tool_invocations", {}))

    # Conversion inputs strictly from validated state (Requirement 4)
    ev_val_dec = state["validated_ev_val_dec"]
    ev_unit_clean = state["validated_ev_unit_clean"]
    record_val_dec = state["record_val_dec"]
    record_unit_clean = state["record_unit_clean"]

    # Invoke MeasurementConversionComparisonTool
    tools["measurement_conversion_tool"] = tools.get("measurement_conversion_tool", 0) + 1
    conv_result = measurement_conversion_tool.invoke({
        "evidence_value": str(ev_val_dec),
        "evidence_unit": str(ev_unit_clean),
        "record_value": str(record_val_dec),
        "record_unit": str(record_unit_clean),
    })

    # Assemble structured comparison response using shared domain logic
    comparison_res = evaluate_and_compare_measurements(
        ev_val_dec=ev_val_dec,  # type: ignore
        ev_unit_clean=ev_unit_clean,  # type: ignore
        record_val_dec=record_val_dec,  # type: ignore
        record_unit_clean=record_unit_clean,  # type: ignore
        raw_rec_val=state["raw_rec_val"],
        raw_rec_unit=state["raw_rec_unit"],
        base_response=state["base_response"],
        evidence_dict=state.get("validated_evidence_dict"),
        extractor_meta=state.get("extractor_meta") or {},
    )

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    timings["convert_and_compare"] = elapsed_ms

    return {
        "node_transitions": transitions,
        "node_timings": timings,
        "tool_invocations": tools,
        "is_terminal": True,
        "terminal_reason": "comparison_completed",
        "final_response": comparison_res,
    }


def node_finalize(state: InvestigationGraphState) -> Dict[str, Any]:
    """Node 6: Finalize graph execution and ensure structured response contract is met."""
    t0 = time.perf_counter()
    transitions = list(state.get("node_transitions", []))
    transitions.append("finalize")
    timings = dict(state.get("node_timings", {}))
    tools = dict(state.get("tool_invocations", {}))

    final_res = state.get("final_response")
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
                not_invoked_reason="Graph produced no terminal response.",
            ),
            "explanation": "StateGraph execution terminated without producing a response.",
        }

    elapsed_ms = round((time.perf_counter() - t0) * 1000.0, 3)
    timings["finalize"] = elapsed_ms

    return {
        "node_transitions": transitions,
        "node_timings": timings,
        "tool_invocations": tools,
        "final_response": final_res,
    }


# ---------------------------------------------------------------------------
# Conditional Routing Functions (Requirement 3)
# ---------------------------------------------------------------------------
def route_after_validate(state: InvestigationGraphState) -> str:
    """Guard transition after record validation: invalid record routes to finalize."""
    if not state.get("is_record_valid", False) or state.get("is_terminal", False):
        return "finalize"
    return "retrieve_evidence"


def route_after_retrieve(state: InvestigationGraphState) -> str:
    """Guard transition after evidence retrieval: missing/conflicting evidence routes to finalize."""
    if state.get("is_terminal", False):
        return "finalize"
    return "extract_measurement"


def route_after_extract(state: InvestigationGraphState) -> str:
    """Guard transition after measurement extraction: extractor abstention/error routes to finalize."""
    if state.get("is_terminal", False):
        return "finalize"
    return "validate_evidence"


def route_after_validate_evidence(state: InvestigationGraphState) -> str:
    """Guard transition after evidence validation: ungrounded/invalid evidence routes to finalize."""
    if not state.get("is_evidence_valid", False) or state.get("is_terminal", False):
        return "finalize"
    return "convert_and_compare"


# ---------------------------------------------------------------------------
# StateGraph Builder (Requirement 3 & 5)
# ---------------------------------------------------------------------------
_COMPILED_GRAPH = None


def build_investigation_graph() -> Any:
    """Construct and compile the controlled StateGraph with guarded transitions."""
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "langgraph is not installed. Install requirements-orchestration.txt (pip install -r requirements-orchestration.txt)."
        )

    builder = StateGraph(InvestigationGraphState)

    # 1. Register explicit nodes
    builder.add_node("validate_record", node_validate_record)
    builder.add_node("retrieve_evidence", node_retrieve_evidence)
    builder.add_node("extract_measurement", node_extract_measurement)
    builder.add_node("validate_evidence", node_validate_evidence)
    builder.add_node("convert_and_compare", node_convert_and_compare)
    builder.add_node("finalize", node_finalize)

    # 2. Add entry edge
    builder.add_edge(START, "validate_record")

    # 3. Add guarded conditional edges
    builder.add_conditional_edges(
        "validate_record",
        route_after_validate,
        {"retrieve_evidence": "retrieve_evidence", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "retrieve_evidence",
        route_after_retrieve,
        {"extract_measurement": "extract_measurement", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "extract_measurement",
        route_after_extract,
        {"validate_evidence": "validate_evidence", "finalize": "finalize"},
    )
    builder.add_conditional_edges(
        "validate_evidence",
        route_after_validate_evidence,
        {"convert_and_compare": "convert_and_compare", "finalize": "finalize"},
    )

    # 4. Final edges to END
    builder.add_edge("convert_and_compare", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


def get_compiled_graph() -> Any:
    """Retrieve or build the compiled LangGraph workflow instance."""
    global _COMPILED_GRAPH
    if _COMPILED_GRAPH is None:
        _COMPILED_GRAPH = build_investigation_graph()
    return _COMPILED_GRAPH


# ---------------------------------------------------------------------------
# Investigation Entrypoint (Requirement 6)
# ---------------------------------------------------------------------------
def investigate_record_langgraph(
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
    """Execute record investigation using the controlled LangGraph StateGraph pipeline."""
    if not LANGGRAPH_AVAILABLE:
        raise ImportError(
            "langgraph is not installed. Install requirements-orchestration.txt (pip install -r requirements-orchestration.txt)."
        )

    repo_root = Path(__file__).resolve().parent.parent
    if extracted_dir is None:
        extracted_dir = repo_root / "data" / "extracted"
    else:
        extracted_dir = Path(extracted_dir)

    if isinstance(record_path, dict):
        record = dict(record_path)
    else:
        rec_path_obj = Path(record_path)
        if not rec_path_obj.exists():
            raise FileNotFoundError(f"Record file not found: {record_path}")
        with open(rec_path_obj, "r", encoding="utf-8") as f:
            record = json.load(f)

    # 1. Initialize base response and clean fields
    base_response, current_record = init_base_response(record)

    # 2. Resolve extractor instance
    if isinstance(extractor, str):
        extractor_name = extractor.lower()
        if extractor_name in ("gemini", "google-genai"):
            extractor_inst = get_extractor("gemini", api_key=gemini_api_key, model=gemini_model)
        else:
            extractor_inst = get_extractor("deterministic")
    else:
        extractor_inst = extractor
        extractor_name = getattr(extractor, "name", "custom")

    retriever_name = getattr(retriever, "name", str(retriever))

    # 3. Construct isolated, unshared initial state (Requirement 2)
    # Credentials and expected answers are strictly omitted
    initial_state: InvestigationGraphState = {
        "record": record,
        "extracted_dir": extracted_dir,
        "retriever_name": retriever_name,
        "extractor_name": extractor_name,
        "extractor_inst": extractor_inst,
        "corpus_id": corpus_id,
        "retriever_kwargs": dict(retriever_kwargs or {}),
        "case_id": base_response["case_id"],
        "record_id": base_response["record_id"],
        "component_id": base_response["component_id"],
        "revision": base_response["revision"],
        "attribute_name": base_response["attribute_name"],
        "current_record": current_record,
        "base_response": base_response,
        "raw_rec_val": current_record["value"],
        "raw_rec_unit": current_record["unit"],
        "is_record_valid": False,
        "is_evidence_valid": False,
        "is_terminal": False,
        "extractor_invoked": False,
        "node_transitions": [],
        "node_timings": {},
        "tool_invocations": {},
    }

    # 4. Execute graph with finite recursion limit (Requirement 5)
    graph = get_compiled_graph()
    output_state = graph.invoke(initial_state, config={"recursion_limit": 10})

    final_resp = output_state["final_response"]
    if return_telemetry:
        telemetry = {
            "node_transitions": output_state.get("node_transitions", []),
            "node_timings": output_state.get("node_timings", {}),
            "tool_invocations": output_state.get("tool_invocations", {}),
            "extractor_invocations": 1 if output_state.get("extractor_invoked") else 0,
            "terminal_reason": output_state.get("terminal_reason"),
        }
        return final_resp, telemetry

    return final_resp
