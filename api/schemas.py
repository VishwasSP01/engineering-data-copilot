"""Pydantic schemas for Engineering Data Copilot FastAPI service."""

from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, model_validator


class HealthResponse(BaseModel):
    """Health check response schema."""
    status: str = "healthy"
    service: str = "engineering-data-copilot"
    version: str = "1.0.0"


class DocumentReferenceRequest(BaseModel):
    """Optional document reference in request."""
    model_config = ConfigDict(extra="ignore")

    document_id: Optional[str] = Field(None, description="Optional document ID")
    filename: Optional[str] = Field(None, description="Supplier document filename")


class InvestigationRequest(BaseModel):
    """Engineering record input schema for investigation."""
    model_config = ConfigDict(extra="ignore")

    component_id: Optional[str] = Field(None, description="Component identifier (e.g. COMP-001)")
    part_number: Optional[str] = Field(None, description="Alternative component/part identifier")
    record_id: Optional[str] = Field(None, description="Unique record identifier")
    case_id: Optional[str] = Field(None, description="Case or batch identifier")
    revision: Optional[str] = Field(None, description="Component or document revision (e.g. 'A')")
    attribute_name: Optional[str] = Field(None, description="Measurement attribute to investigate (e.g. 'thickness')")
    attribute: Optional[str] = Field(None, description="Alias for attribute_name")
    measurement: Optional[str] = Field(None, description="Alias for attribute_name")
    recorded_value: Union[float, int] = Field(..., description="Currently recorded numeric measurement value")
    recorded_unit: str = Field(..., description="Currently recorded measurement unit (e.g. 'mm', 'cm')")
    document_reference: Optional[Union[DocumentReferenceRequest, Dict[str, Any], str]] = Field(
        None,
        description="Optional document reference metadata"
    )
    extractor: Optional[str] = Field(
        None,
        description="Optional extractor selection: 'deterministic' (default) or 'gemini'"
    )

    @model_validator(mode="after")
    def validate_record_fields(self) -> "InvestigationRequest":
        comp = (self.component_id or self.part_number or "").strip()
        if not comp:
            raise ValueError("Field 'component_id' or 'part_number' is required.")

        attr = (self.attribute_name or self.attribute or self.measurement or "").strip()
        if not attr:
            raise ValueError("Field 'attribute_name' is required.")

        unit = (self.recorded_unit or "").strip()
        if not unit:
            raise ValueError("Field 'recorded_unit' is required.")

        if self.extractor is not None:
            ext_clean = str(self.extractor).strip().lower()
            if ext_clean not in ("deterministic", "gemini"):
                raise ValueError(f"Extractor '{self.extractor}' is invalid. Supported: 'deterministic', 'gemini'.")

        return self

    def to_record_dict(self) -> Dict[str, Any]:
        """Convert validated request into normalized engineering record dictionary."""
        comp = self.component_id or self.part_number
        attr = self.attribute_name or self.attribute or self.measurement

        rec: Dict[str, Any] = {
            "component_id": comp,
            "part_number": self.part_number or comp,
            "attribute_name": attr,
            "recorded_value": self.recorded_value,
            "recorded_unit": self.recorded_unit.strip(),
        }

        if self.record_id:
            rec["record_id"] = self.record_id
        if self.case_id:
            rec["case_id"] = self.case_id
        if self.revision:
            rec["revision"] = self.revision

        if self.document_reference:
            if isinstance(self.document_reference, DocumentReferenceRequest):
                rec["document_reference"] = self.document_reference.model_dump(exclude_none=True)
            elif isinstance(self.document_reference, dict):
                # Ignore client-supplied internal filesystem paths
                cleaned = {k: v for k, v in self.document_reference.items() if k != "filepath"}
                rec["document_reference"] = cleaned
            elif isinstance(self.document_reference, str):
                rec["document_reference"] = {"filename": self.document_reference}

        return rec


class CurrentRecord(BaseModel):
    """Currently recorded measurement in engineering record."""
    value: Any = None
    unit: Optional[str] = None


class EvidenceMeasurement(BaseModel):
    """Extracted evidence measurement value and unit."""
    value: float
    unit: str


class UnitConversion(BaseModel):
    """Deterministic conversion details."""
    supplier_extracted_value: float
    supplier_extracted_unit: str
    target_unit: str
    multiplier: float
    calculation: str
    method: str


class ProposedCorrection(BaseModel):
    """Proposed correction details if mismatch detected."""
    value: float
    unit: str
    conversion: Optional[UnitConversion] = None


class EvidenceDetails(BaseModel):
    """Retrieved evidence passage citation."""
    model_config = ConfigDict(extra="allow")

    document_filename: Optional[str] = None
    page_number: Optional[int] = None
    supporting_passage: Optional[str] = None
    model_quote: Optional[str] = None
    alignment: Optional[str] = None


class ExtractorMetadata(BaseModel):
    """Extractor execution metadata."""
    provider: str
    model: Optional[str] = None
    mode: str
    is_fallback: bool = False
    call_duration_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    token_usage_reason: Optional[str] = None
    status: Optional[str] = None
    error_type: Optional[str] = None


class InvestigationResponse(BaseModel):
    """Investigation result response schema."""
    model_config = ConfigDict(extra="allow")

    case_id: Optional[str] = None
    record_id: Optional[str] = None
    component_id: Optional[str] = None
    revision: Optional[str] = None
    attribute_name: Optional[str] = None
    current_record: Optional[CurrentRecord] = None
    source_record_modified: bool = False
    retrieval_status: Optional[str] = None
    context_type: Optional[str] = None
    status: str
    outcome: str
    evidence_measurement: Optional[EvidenceMeasurement] = None
    proposed_correction: Optional[ProposedCorrection] = None
    evidence: Optional[EvidenceDetails] = None
    extractor: ExtractorMetadata
    explanation: str


class ErrorResponse(BaseModel):
    """Structured error response schema."""
    error_code: str
    detail: Any
