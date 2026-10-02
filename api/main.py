"""FastAPI investigation service for Engineering Data Copilot."""

import asyncio
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Union

from fastapi import Depends, FastAPI, Query, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

# Add repo root to sys.path to import scripts package
REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.schemas import (
    ErrorResponse,
    HealthResponse,
    InvestigationRequest,
    InvestigationResponse,
)
from scripts.extractors import BaseMeasurementExtractor
from scripts.investigate_record import investigate_record

app = FastAPI(
    title="Engineering Data Copilot API",
    description="Minimal investigation service exposing evidence retrieval and measurement verification workflows.",
    version="1.0.0",
)

# Server-configured document corpus; clients cannot supply filesystem paths
CORPUS_DIR = REPO_ROOT / "data" / "extracted"


def get_extractor_dependency() -> Optional[BaseMeasurementExtractor]:
    """Dependency injection hook allowing tests to supply mock extractors without live API calls."""
    return None


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Return structured JSON on request validation failure (HTTP 422)."""
    return JSONResponse(
        status_code=422,
        content={
            "error_code": "VALIDATION_ERROR",
            "detail": jsonable_encoder(exc.errors()),
        },
    )


@app.get(
    "/health",
    response_model=HealthResponse,
    summary="Service Health Check",
    tags=["Health"],
)
async def health_check() -> HealthResponse:
    """Return simple service health status without calling external services or requiring credentials."""
    return HealthResponse(
        status="healthy",
        service="engineering-data-copilot",
        version="1.0.0",
    )


@app.post(
    "/investigations",
    response_model=InvestigationResponse,
    responses={
        200: {
            "model": InvestigationResponse,
            "description": "Investigation outcome (correction_proposed, no_change, or data abstention)",
        },
        422: {
            "model": ErrorResponse,
            "description": "Malformed request payload or invalid extractor selection",
        },
        502: {
            "model": ErrorResponse,
            "description": "Upstream AI provider request failure",
        },
        503: {
            "model": ErrorResponse,
            "description": "Requested provider not configured (missing credentials or dependencies)",
        },
    },
    summary="Investigate Engineering Record",
    tags=["Investigations"],
)
async def create_investigation(
    payload: InvestigationRequest,
    extractor: Optional[str] = Query(
        None,
        description="Measurement extractor selection: 'deterministic' (default) or 'gemini'",
    ),
    extractor_override: Optional[BaseMeasurementExtractor] = Depends(get_extractor_dependency),
) -> Any:
    """Investigate an engineering record against server-configured supplier evidence.
    
    Proposes evidence-backed unit corrections or abstains safely if evidence is missing or ambiguous.
    """
    # Resolve selected extractor: query param > payload field > default 'deterministic'
    chosen_extractor = extractor or payload.extractor or "deterministic"
    chosen_extractor = chosen_extractor.strip().lower()

    if chosen_extractor not in ("deterministic", "gemini"):
        return JSONResponse(
            status_code=422,
            content={
                "error_code": "INVALID_EXTRACTOR",
                "detail": f"Extractor '{chosen_extractor}' is not supported. Supported extractors: 'deterministic', 'gemini'.",
            },
        )

    # Active extractor instance or string name
    active_extractor: Union[str, BaseMeasurementExtractor] = (
        extractor_override if extractor_override is not None else chosen_extractor
    )

    record_dict = payload.to_record_dict()

    # Execute investigation off the async event loop to avoid blocking concurrent requests
    result = await asyncio.to_thread(
        investigate_record,
        record_dict,
        extracted_dir=CORPUS_DIR,
        extractor=active_extractor,
    )

    # Check for provider configuration or request failures using structured metadata
    extractor_meta = result.get("extractor", {})
    if extractor_meta.get("status") == "error":
        error_type = extractor_meta.get("error_type")
        if error_type == "CONFIGURATION_ERROR":
            return JSONResponse(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                content={
                    "error_code": "PROVIDER_NOT_CONFIGURED",
                    "detail": "Requested AI provider is not configured or credentials are missing.",
                },
            )
        elif error_type == "PROVIDER_ERROR":
            return JSONResponse(
                status_code=status.HTTP_502_BAD_GATEWAY,
                content={
                    "error_code": "PROVIDER_REQUEST_FAILED",
                    "detail": "Upstream AI provider request failed.",
                },
            )

    return result
