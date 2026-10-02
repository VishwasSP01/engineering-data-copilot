#!/usr/bin/env python3
import warnings
warnings.filterwarnings("ignore")

"""
Measurement extractor interface and implementations for Engineering Data Copilot.

Step 8 implementation:
- Defines structured Pydantic schema (MeasurementExtractionResponse) for model extraction.
- Defines BaseMeasurementExtractor interface.
- Preserves DeterministicMeasurementExtractor as default baseline.
- Implements GeminiMeasurementExtractor using the official google-genai SDK.
- Extracts nominal numeric value and unit while leaving unit conversion and comparison
  strictly to deterministic downstream logic.
- Collects execution metadata: provider, model, latency, and token usage.
- Never prints or leaks credentials.
"""

import os
import re
import time
import warnings
from abc import ABC, abstractmethod
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, Literal, Optional, Tuple, Union

# Suppress known environment deprecation warnings from google-auth and urllib3
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

from pydantic import BaseModel, Field, ValidationError, model_validator

# google-genai imports
try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None  # type: ignore
    types = None  # type: ignore
    APIError = Exception  # type: ignore
    GENAI_AVAILABLE = False


SUPPORTED_UNITS = {"mm", "cm"}


class MeasurementExtractionResponse(BaseModel):
    """Structured Pydantic schema for model measurement extraction."""
    status: Literal["found", "insufficient", "ambiguous"] = Field(
        ...,
        description="Extraction status: 'found' if requested measurement is present and unambiguous; 'insufficient' if not found; 'ambiguous' if conflicting measurements exist."
    )
    measurement_name: Optional[str] = Field(
        None,
        description="The name of the requested measurement (e.g. 'thickness', 'width'). Required if status is 'found'."
    )
    value: Optional[str] = Field(
        None,
        description="The numeric measurement value represented as a decimal string (e.g. '0.8', '25.0'). Required if status is 'found'."
    )
    unit: Optional[str] = Field(
        None,
        description="The measurement unit (e.g. 'mm', 'cm'). Required if status is 'found'."
    )
    quote: Optional[str] = Field(
        None,
        description="The exact verbatim supporting quote from the evidence passage where the measurement was found. Required if status is 'found'."
    )

    @model_validator(mode="after")
    def validate_fields_on_success(self) -> "MeasurementExtractionResponse":
        if self.status == "found":
            missing = []
            if not self.measurement_name or not self.measurement_name.strip():
                missing.append("measurement_name")
            if not self.value or not self.value.strip():
                missing.append("value")
            if not self.unit or not self.unit.strip():
                missing.append("unit")
            if not self.quote or not self.quote.strip():
                missing.append("quote")

            if missing:
                raise ValueError(f"Fields {missing} are required when extraction status is 'found'.")

            try:
                Decimal(self.value.strip())
            except (InvalidOperation, TypeError):
                raise ValueError(f"Value '{self.value}' cannot be parsed as a decimal number.")

        return self


@dataclass
class ExtractorResult:
    """Standardized result returned by all measurement extractors."""
    status: str  # "found", "insufficient", "ambiguous", "error"
    measurement_name: Optional[str] = None
    value: Optional[Decimal] = None
    unit: Optional[str] = None
    quote: Optional[str] = None
    error_message: Optional[str] = None
    error_type: Optional[str] = None  # "CONFIGURATION_ERROR", "PROVIDER_ERROR"

    # Model & Execution Metadata
    provider: str = "deterministic"
    model: Optional[str] = None
    is_fallback: bool = False
    call_duration_ms: float = 0.0
    token_usage: Optional[Dict[str, int]] = None
    token_usage_reason: Optional[str] = None
    raw_response: Optional[str] = None


class BaseMeasurementExtractor(ABC):
    """Abstract base interface for measurement extractors."""

    @abstractmethod
    def extract_measurement(
        self,
        evidence_passage: str,
        attribute_name: str
    ) -> ExtractorResult:
        """Extract measurement value, unit, and quote for the given attribute from evidence passage."""
        pass


def parse_labelled_tuple(
    evidence_passage: str,
    attribute_name: str
) -> Optional[Tuple[Optional[Decimal], Optional[str], Optional[str], Optional[str]]]:
    """Parse labelled measurement tuples such as:
    '(length, width, thickness): 60 mm x 40 mm x 6 mm'
    
    Associates each label with its corresponding value.
    Does not select the first number appearing after the attribute keyword.
    If correspondence is unclear, returns an error message without a correction.
    Generic to any requested attribute.

    Returns:
        None if no labelled tuple structure matching attribute_name is found.
        (value, unit, quote, error_message) if a tuple structure is identified.
        If error_message is not None, value and unit will be None (unclear mapping -> abstain).
    """
    attr_clean = attribute_name.strip().lower()

    for line in evidence_passage.splitlines():
        line_clean = line.strip()
        if not line_clean or attr_clean not in line_clean.lower():
            continue

        # Look for a delimiter ':' or '='
        m_delim = re.search(r'[:=]', line_clean)
        if not m_delim:
            continue

        header = line_clean[:m_delim.start()].strip()
        body = line_clean[m_delim.end():].strip()
        if not header or not body:
            continue

        # Check for label group in parentheses, brackets, or as comma/x-separated header
        m_paren = re.search(r'[\(\[]([^\)\]]+)[\)\]]', header)
        if m_paren:
            labels_str = m_paren.group(1).strip()
        else:
            labels_str = header

        # Extract labels separated by commas, 'x', or '/'
        if ',' in labels_str:
            labels = [l.strip().lower() for l in labels_str.split(',') if l.strip()]
        elif re.search(r'\s+[xX×/]\s+', labels_str) and not any(ch.isdigit() for ch in labels_str):
            labels = [l.strip().lower() for l in re.split(r'\s+[xX×/]\s+', labels_str) if l.strip()]
        else:
            continue

        # A tuple requires at least two distinct labels
        if len(labels) < 2:
            continue

        # Check if requested attribute matches any label in the sequence
        matching_indices = []
        for idx, lbl in enumerate(labels):
            lbl_clean = re.sub(r'^(?:nominal|package|component)\s+', '', lbl).strip()
            if attr_clean == lbl or attr_clean == lbl_clean or attr_clean.split()[-1] == lbl_clean or lbl_clean == attr_clean.split()[-1]:
                matching_indices.append(idx)

        if not matching_indices:
            continue

        # Unclear correspondence if attribute matches multiple positions in tuple
        if len(matching_indices) > 1:
            return None, None, line_clean, f"Unclear tuple mapping: attribute '{attribute_name}' matches multiple label positions {matching_indices}."

        target_idx = matching_indices[0]

        # Extract measurement values from body
        # Split body by 'x', 'X', '×', ',', or 'and'
        raw_items = re.findall(r'(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)?', body)
        if not raw_items:
            return None, None, line_clean, "Unclear tuple mapping: no numeric values found in tuple body."

        # Handle shared trailing unit (e.g., '60 x 40 x 6 mm')
        has_units = [bool(u) for _, u in raw_items]
        last_unit = raw_items[-1][1] if raw_items else ""
        resolved_items = []
        if not all(has_units) and last_unit:
            for val, u in raw_items:
                resolved_items.append((val, u if u else last_unit))
        else:
            resolved_items = raw_items

        # Verify 1-to-1 correspondence between labels and values
        if len(labels) != len(resolved_items):
            return None, None, line_clean, f"Unclear tuple mapping: label count ({len(labels)}) does not match value count ({len(resolved_items)})."

        target_val_str, target_unit_str = resolved_items[target_idx]
        if not target_unit_str:
            return None, None, line_clean, f"Unclear tuple mapping: no unit found for measurement at position {target_idx}."

        try:
            val_dec = Decimal(target_val_str)
        except InvalidOperation:
            return None, None, line_clean, f"Unclear tuple mapping: could not convert '{target_val_str}' to Decimal."

        return val_dec, target_unit_str.lower(), line_clean, None

    return None


class DeterministicMeasurementExtractor(BaseMeasurementExtractor):
    """Deterministic regex-based measurement extractor (default baseline)."""

    def extract_measurement(
        self,
        evidence_passage: str,
        attribute_name: str
    ) -> ExtractorResult:
        t0 = time.perf_counter()

        if not evidence_passage:
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            return ExtractorResult(
                status="insufficient",
                error_message="Empty evidence passage provided.",
                provider="deterministic",
                model=None,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason="Token usage not applicable for deterministic extractor."
            )

        # Pattern 0: Check for explicit labelled tuple first (e.g. '(length, width, thickness): 60 mm x 40 mm x 6 mm')
        tuple_res = parse_labelled_tuple(evidence_passage, attribute_name)
        if tuple_res is not None:
            val_dec, raw_unit, quote, err = tuple_res
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            if err is not None:
                return ExtractorResult(
                    status="error",
                    error_message=err,
                    provider="deterministic",
                    model=None,
                    call_duration_ms=duration_ms,
                    token_usage=None,
                    token_usage_reason="Token usage not applicable for deterministic extractor."
                )
            return ExtractorResult(
                status="found",
                measurement_name=attribute_name,
                value=val_dec,
                unit=raw_unit,
                quote=quote,
                provider="deterministic",
                model=None,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason="Token usage not applicable for deterministic extractor."
            )

        # Pattern 1: attribute followed by number and unit
        pattern_fwd = rf'\b{re.escape(attribute_name)}\b[^\n.!?]*?(?:[:=]|\bis\b)?\s*(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)'
        m = re.search(pattern_fwd, evidence_passage, re.IGNORECASE)

        # Pattern 2: number and unit followed by attribute
        if not m:
            pattern_rev = rf'(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)\s+(?:[A-Za-z0-9_-]+\s+)*{re.escape(attribute_name)}'
            m = re.search(pattern_rev, evidence_passage, re.IGNORECASE)

        # Pattern 3: direct measurement on a standalone line
        if not m:
            pattern_line = r'^\s*(?:[A-Za-z0-9_-]+\s+)*(\d+(?:\.\d+)?)\s*([a-zA-Zµ°Ω%]+)'
            m = re.search(pattern_line, evidence_passage, re.IGNORECASE)

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        if not m:
            return ExtractorResult(
                status="insufficient",
                error_message=f"Could not find numeric measurement for '{attribute_name}' in evidence passage.",
                provider="deterministic",
                model=None,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason="Token usage not applicable for deterministic extractor."
            )

        raw_val = m.group(1)
        raw_unit = m.group(2).lower()
        quote = m.group(0).strip()

        try:
            val_dec = Decimal(raw_val)
        except InvalidOperation:
            return ExtractorResult(
                status="error",
                error_message=f"Could not parse numeric value '{raw_val}' as Decimal.",
                provider="deterministic",
                model=None,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason="Token usage not applicable for deterministic extractor."
            )

        return ExtractorResult(
            status="found",
            measurement_name=attribute_name,
            value=val_dec,
            unit=raw_unit,
            quote=quote,
            provider="deterministic",
            model=None,
            call_duration_ms=duration_ms,
            token_usage=None,
            token_usage_reason="Token usage not applicable for deterministic extractor."
        )


def build_extraction_prompt(evidence_passage: str, attribute_name: str) -> str:
    """Build prompt supplying ONLY the requested measurement and retrieved evidence passage.
    
    Adheres strictly to Step 8 requirements:
    - Only requested measurement name and retrieved evidence passage are supplied.
    - Explicitly instructs the model NOT to perform any unit conversion, arithmetic, or correction.
    """
    return (
        f"You are a technical document extraction assistant.\n"
        f"Your task is to extract the numeric measurement value and unit for a specific requested attribute "
        f"from the provided evidence passage.\n\n"
        f"Strict Instructions:\n"
        f"1. Extract ONLY from the provided evidence passage. Do NOT guess, assume, or extrapolate.\n"
        f"2. Do NOT convert units. Extract the exact value and unit as stated in the evidence.\n"
        f"3. Do NOT calculate or propose any corrections.\n"
        f"4. If the measurement is clearly stated, set status to 'found', provide the measurement name, "
        f"the numeric value as a decimal string, the unit, and the exact verbatim quote from the passage.\n"
        f"5. If the requested measurement is not present or cannot be determined, set status to 'insufficient'.\n"
        f"6. If multiple conflicting values exist for the measurement, set status to 'ambiguous'.\n\n"
        f"Requested Measurement: {attribute_name}\n\n"
        f"Evidence Passage:\n\"\"\"\n{evidence_passage}\n\"\"\"\n"
    )


def load_dotenv(dotenv_path: Optional[Union[str, Path]] = None) -> None:
    """Load key-value pairs from repository-root .env file into os.environ.
    
    Preserves existing shell environment variables (does not overwrite).
    """
    if dotenv_path is None:
        dotenv_path = Path(__file__).resolve().parent.parent / ".env"
    else:
        dotenv_path = Path(dotenv_path)

    if not dotenv_path.is_file():
        return

    try:
        with open(dotenv_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip()
                if len(val) >= 2 and (
                    (val.startswith('"') and val.endswith('"')) or
                    (val.startswith("'") and val.endswith("'"))
                ):
                    val = val[1:-1]
                # Preserve existing environment variables
                if key and key not in os.environ:
                    os.environ[key] = val
    except Exception:
        pass


# Automatically load .env if present upon module import
load_dotenv()


PLACEHOLDER_KEYS = {"REPLACE_ME", "your-api-key-here", "YOUR_API_KEY"}


class GeminiMeasurementExtractor(BaseMeasurementExtractor):
    """Gemini measurement extractor using official google-genai SDK."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        client: Optional[Any] = None,
        timeout: float = 10.0,
    ):
        load_dotenv()
        self.model = model or os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
        self.timeout = timeout
        self.client = client

        if self.client is None and GENAI_AVAILABLE:
            resolved_key = api_key or os.environ.get("GEMINI_API_KEY")
            if resolved_key and resolved_key.strip() not in PLACEHOLDER_KEYS:
                timeout_ms = int(self.timeout * 1000)
                retry_options = types.HttpRetryOptions(attempts=1)
                http_options = types.HttpOptions(timeout=timeout_ms, retry_options=retry_options)
                self.client = genai.Client(api_key=resolved_key.strip(), http_options=http_options)

    def extract_measurement(
        self,
        evidence_passage: str,
        attribute_name: str
    ) -> ExtractorResult:
        t0 = time.perf_counter()

        if not GENAI_AVAILABLE:
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            return ExtractorResult(
                status="error",
                error_message="google-genai SDK is not installed or available in this environment.",
                error_type="CONFIGURATION_ERROR",
                provider="google-genai",
                model=self.model,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason="google-genai SDK not available."
            )

        if self.client is None:
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            resolved_key = os.environ.get("GEMINI_API_KEY", "")
            if resolved_key.strip() in PLACEHOLDER_KEYS:
                err_msg = "GEMINI_API_KEY is not configured (contains placeholder 'REPLACE_ME'). Please update .env or set GEMINI_API_KEY in your shell."
            else:
                err_msg = "GEMINI_API_KEY environment variable is not set and no client was provided."
            return ExtractorResult(
                status="error",
                error_message=err_msg,
                error_type="CONFIGURATION_ERROR",
                provider="google-genai",
                model=self.model,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason="Credentials missing or placeholder; API was not invoked."
            )

        prompt = build_extraction_prompt(evidence_passage, attribute_name)

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=MeasurementExtractionResponse,
            temperature=0.0
        )

        try:
            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config
            )
        except Exception as exc:
            duration_ms = round((time.perf_counter() - t0) * 1000, 2)
            return ExtractorResult(
                status="error",
                error_message=f"Gemini API call failed: {exc}",
                error_type="PROVIDER_ERROR",
                provider="google-genai",
                model=self.model,
                call_duration_ms=duration_ms,
                token_usage=None,
                token_usage_reason=f"API error occurred: {type(exc).__name__}"
            )

        duration_ms = round((time.perf_counter() - t0) * 1000, 2)

        # Extract token usage if available
        token_usage = None
        token_usage_reason = None
        usage_meta = getattr(response, "usage_metadata", None)
        if usage_meta:
            token_usage = {
                "prompt_tokens": getattr(usage_meta, "prompt_token_count", 0),
                "candidates_tokens": getattr(usage_meta, "candidates_token_count", 0),
                "total_tokens": getattr(usage_meta, "total_token_count", 0)
            }
        else:
            token_usage_reason = "Token usage metadata not returned by response."

        # Parse structured output
        raw_text = getattr(response, "text", "") or ""
        parsed_obj: Optional[MeasurementExtractionResponse] = None

        if hasattr(response, "parsed") and isinstance(response.parsed, MeasurementExtractionResponse):
            parsed_obj = response.parsed
        else:
            cleaned_text = raw_text.strip()
            if cleaned_text.startswith("```json"):
                cleaned_text = cleaned_text[7:]
            elif cleaned_text.startswith("```"):
                cleaned_text = cleaned_text[3:]
            if cleaned_text.endswith("```"):
                cleaned_text = cleaned_text[:-3]
            cleaned_text = cleaned_text.strip()

            try:
                parsed_obj = MeasurementExtractionResponse.model_validate_json(cleaned_text)
            except (ValidationError, Exception) as exc:
                return ExtractorResult(
                    status="error",
                    error_message=f"Malformed model output could not be validated against schema: {exc}",
                    error_type="PROVIDER_ERROR",
                    provider="google-genai",
                    model=self.model,
                    call_duration_ms=duration_ms,
                    token_usage=token_usage,
                    token_usage_reason=token_usage_reason,
                    raw_response=raw_text
                )

        if parsed_obj.status in ("insufficient", "ambiguous"):
            return ExtractorResult(
                status=parsed_obj.status,
                measurement_name=parsed_obj.measurement_name,
                quote=parsed_obj.quote,
                provider="google-genai",
                model=self.model,
                call_duration_ms=duration_ms,
                token_usage=token_usage,
                token_usage_reason=token_usage_reason,
                raw_response=raw_text
            )

        try:
            val_dec = Decimal(parsed_obj.value.strip()) if parsed_obj.value else None
        except (InvalidOperation, TypeError):
            return ExtractorResult(
                status="error",
                error_message=f"Extracted value '{parsed_obj.value}' could not be converted to Decimal.",
                error_type="PROVIDER_ERROR",
                provider="google-genai",
                model=self.model,
                call_duration_ms=duration_ms,
                token_usage=token_usage,
                token_usage_reason=token_usage_reason,
                raw_response=raw_text
            )

        return ExtractorResult(
            status="found",
            measurement_name=parsed_obj.measurement_name,
            value=val_dec,
            unit=parsed_obj.unit.strip().lower() if parsed_obj.unit else None,
            quote=parsed_obj.quote.strip() if parsed_obj.quote else None,
            provider="google-genai",
            model=self.model,
            call_duration_ms=duration_ms,
            token_usage=token_usage,
            token_usage_reason=token_usage_reason,
            raw_response=raw_text
        )


def get_extractor(name: str = "deterministic", **kwargs) -> BaseMeasurementExtractor:
    """Factory helper to obtain an extractor instance."""
    normalized = name.strip().lower()
    if normalized == "deterministic":
        return DeterministicMeasurementExtractor()
    elif normalized in ("gemini", "google-genai"):
        return GeminiMeasurementExtractor(**kwargs)
    else:
        raise ValueError(f"Unknown extractor '{name}'. Supported: 'deterministic', 'gemini'.")
