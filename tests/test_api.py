"""Offline API integration tests for Engineering Data Copilot FastAPI service."""

import hashlib
import json
import os
import unittest
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi.testclient import TestClient

from api.main import app, get_extractor_dependency
from api.schemas import HealthResponse, InvestigationResponse
from scripts.extractors import BaseMeasurementExtractor, ExtractorResult
from scripts.investigate_record import investigate_record

REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLE_RECORD_PATH = REPO_ROOT / "data" / "records" / "unit-mismatch-001.json"
EXTRACTED_DOC_PATH = REPO_ROOT / "data" / "extracted" / "supplier-COMP-001.json"


def compute_sha256(filepath: Path) -> str:
    """Compute sha256 checksum of a file."""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(8192):
            h.update(chunk)
    return h.hexdigest()


class MockErrorExtractor(BaseMeasurementExtractor):
    """Mock extractor returning designated error results without network activity."""

    def __init__(self, error_type: str, error_message: str):
        self.error_type = error_type
        self.error_message = error_message
        self.provider = "google-genai"
        self.model = "mock-model"

    def extract_measurement(self, evidence_passage: str, attribute_name: str) -> ExtractorResult:
        return ExtractorResult(
            status="error",
            error_message=self.error_message,
            error_type=self.error_type,
            provider=self.provider,
            model=self.model,
            call_duration_ms=1.5,
            token_usage=None,
            token_usage_reason="Mock error extractor",
        )


class TestInvestigationAPI(unittest.TestCase):
    """Offline test suite for FastAPI investigation endpoints."""

    def setUp(self):
        self.client = TestClient(app)
        app.dependency_overrides.clear()
        with open(SAMPLE_RECORD_PATH, "r", encoding="utf-8") as f:
            self.sample_payload = json.load(f)

    def tearDown(self):
        app.dependency_overrides.clear()

    def test_health_check_no_dependencies(self):
        """GET /health returns 200 without credentials or external calls."""
        response = self.client.get("/health")
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "healthy")
        self.assertEqual(data["service"], "engineering-data-copilot")
        self.assertEqual(data["version"], "1.0.0")

    def test_investigation_sample_correction_deterministic(self):
        """POST /investigations with deterministic extractor reproduces 0.8 mm -> 8.0 mm correction."""
        response = self.client.post("/investigations", json=self.sample_payload)
        self.assertEqual(response.status_code, 200)
        data = response.json()

        self.assertEqual(data["outcome"], "correction_proposed")
        self.assertEqual(data["status"], "correction_proposed")
        self.assertIsNotNone(data["proposed_correction"])
        self.assertEqual(data["proposed_correction"]["value"], 8.0)
        self.assertEqual(data["proposed_correction"]["unit"], "mm")

        # Verify evidence citation
        self.assertEqual(data["evidence"]["document_filename"], "supplier-COMP-001.pdf")
        self.assertEqual(data["evidence"]["page_number"], 1)
        self.assertEqual(data["evidence"]["supporting_passage"], "Component thickness: 0.8 cm.")

        # Verify extractor metadata
        self.assertEqual(data["extractor"]["provider"], "deterministic")
        self.assertEqual(data["extractor"]["mode"], "deterministic")

    def test_api_matches_cli_concordance(self):
        """API investigation output matches CLI investigate_record output for identical input."""
        cli_result = investigate_record(SAMPLE_RECORD_PATH, extractor="deterministic")
        api_response = self.client.post("/investigations", json=self.sample_payload)

        self.assertEqual(api_response.status_code, 200)
        api_data = api_response.json()

        self.assertEqual(api_data["outcome"], cli_result["outcome"])
        self.assertEqual(api_data["status"], cli_result["status"])
        self.assertEqual(api_data["proposed_correction"], cli_result["proposed_correction"])
        self.assertEqual(api_data["evidence_measurement"], cli_result["evidence_measurement"])
        self.assertEqual(
            api_data["evidence"]["document_filename"],
            cli_result["evidence"]["document_filename"]
        )
        self.assertEqual(
            api_data["evidence"]["page_number"],
            cli_result["evidence"]["page_number"]
        )
        self.assertEqual(
            api_data["evidence"]["supporting_passage"],
            cli_result["evidence"]["supporting_passage"]
        )
        self.assertEqual(api_data["explanation"], cli_result["explanation"])

    def test_malformed_requests_rejected_with_422(self):
        """Malformed requests (missing fields, invalid numbers, bad extractors) return HTTP 422."""
        # 1. Missing component identifier
        bad_payload_1 = {
            "attribute_name": "thickness",
            "recorded_value": 0.8,
            "recorded_unit": "mm",
        }
        res1 = self.client.post("/investigations", json=bad_payload_1)
        self.assertEqual(res1.status_code, 422)
        self.assertEqual(res1.json()["error_code"], "VALIDATION_ERROR")

        # 2. Missing attribute name
        bad_payload_2 = {
            "component_id": "COMP-001",
            "recorded_value": 0.8,
            "recorded_unit": "mm",
        }
        res2 = self.client.post("/investigations", json=bad_payload_2)
        self.assertEqual(res2.status_code, 422)
        self.assertEqual(res2.json()["error_code"], "VALIDATION_ERROR")

        # 3. Non-numeric recorded value
        bad_payload_3 = {
            "component_id": "COMP-001",
            "attribute_name": "thickness",
            "recorded_value": "not-a-number",
            "recorded_unit": "mm",
        }
        res3 = self.client.post("/investigations", json=bad_payload_3)
        self.assertEqual(res3.status_code, 422)
        self.assertEqual(res3.json()["error_code"], "VALIDATION_ERROR")

        # 4. Missing recorded value
        bad_payload_4 = {
            "component_id": "COMP-001",
            "attribute_name": "thickness",
            "recorded_unit": "mm",
        }
        res4 = self.client.post("/investigations", json=bad_payload_4)
        self.assertEqual(res4.status_code, 422)
        self.assertEqual(res4.json()["error_code"], "VALIDATION_ERROR")

        # 5. Unsupported extractor in query parameter
        res5 = self.client.post(
            "/investigations",
            params={"extractor": "unsupported-extractor"},
            json=self.sample_payload
        )
        self.assertEqual(res5.status_code, 422)
        self.assertEqual(res5.json()["error_code"], "INVALID_EXTRACTOR")

        # 6. Unsupported extractor in request body
        bad_payload_6 = {**self.sample_payload, "extractor": "unsupported-extractor"}
        res6 = self.client.post("/investigations", json=bad_payload_6)
        self.assertEqual(res6.status_code, 422)
        self.assertEqual(res6.json()["error_code"], "VALIDATION_ERROR")

    def test_business_abstentions_return_200(self):
        """Data issues (unknown component, revision mismatch, unsupported unit) return HTTP 200 without correction."""
        # Unknown component -> insufficient_evidence
        unknown_comp_payload = {
            "component_id": "COMP-999-DOES-NOT-EXIST",
            "attribute_name": "thickness",
            "recorded_value": 0.8,
            "recorded_unit": "mm",
        }
        res_comp = self.client.post("/investigations", json=unknown_comp_payload)
        self.assertEqual(res_comp.status_code, 200)
        data_comp = res_comp.json()
        self.assertEqual(data_comp["outcome"], "insufficient_evidence")
        self.assertIsNone(data_comp["proposed_correction"])

        # Revision mismatch -> insufficient_evidence
        rev_mismatch_payload = {
            "component_id": "COMP-001",
            "revision": "REV-99",
            "attribute_name": "thickness",
            "recorded_value": 0.8,
            "recorded_unit": "mm",
        }
        res_rev = self.client.post("/investigations", json=rev_mismatch_payload)
        self.assertEqual(res_rev.status_code, 200)
        data_rev = res_rev.json()
        self.assertEqual(data_rev["outcome"], "insufficient_evidence")
        self.assertIsNone(data_rev["proposed_correction"])

        # Unsupported unit -> needs_review
        unsupported_unit_payload = {
            "component_id": "COMP-001",
            "attribute_name": "thickness",
            "recorded_value": 0.8,
            "recorded_unit": "in",  # inches unsupported
        }
        res_unit = self.client.post("/investigations", json=unsupported_unit_payload)
        self.assertEqual(res_unit.status_code, 200)
        data_unit = res_unit.json()
        self.assertEqual(data_unit["outcome"], "needs_review")
        self.assertIsNone(data_unit["proposed_correction"])

    def test_provider_configuration_failure_returns_503(self):
        """Missing credentials or unavailable provider returns sanitized HTTP 503."""
        mock_config_error = MockErrorExtractor(
            error_type="CONFIGURATION_ERROR",
            error_message="GEMINI_API_KEY environment variable is not configured."
        )
        app.dependency_overrides[get_extractor_dependency] = lambda: mock_config_error

        res = self.client.post(
            "/investigations",
            params={"extractor": "gemini"},
            json=self.sample_payload
        )
        self.assertEqual(res.status_code, 503)
        data = res.json()
        self.assertEqual(data["error_code"], "PROVIDER_NOT_CONFIGURED")
        self.assertIn("not configured", data["detail"])

    def test_provider_request_failure_returns_502(self):
        """Upstream AI provider errors return sanitized HTTP 502."""
        mock_provider_error = MockErrorExtractor(
            error_type="PROVIDER_ERROR",
            error_message="Gemini API call failed: 503 Service Unavailable"
        )
        app.dependency_overrides[get_extractor_dependency] = lambda: mock_provider_error

        res = self.client.post(
            "/investigations",
            params={"extractor": "gemini"},
            json=self.sample_payload
        )
        self.assertEqual(res.status_code, 502)
        data = res.json()
        self.assertEqual(data["error_code"], "PROVIDER_REQUEST_FAILED")
        self.assertEqual(data["detail"], "Upstream AI provider request failed.")

    def test_immutability_of_records_and_documents(self):
        """Verification that investigation requests do not alter records or documents."""
        record_hash_before = compute_sha256(SAMPLE_RECORD_PATH)
        doc_hash_before = compute_sha256(EXTRACTED_DOC_PATH)

        res = self.client.post("/investigations", json=self.sample_payload)
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.json()["source_record_modified"])

        record_hash_after = compute_sha256(SAMPLE_RECORD_PATH)
        doc_hash_after = compute_sha256(EXTRACTED_DOC_PATH)

        self.assertEqual(record_hash_before, record_hash_after)
        self.assertEqual(doc_hash_before, doc_hash_after)


if __name__ == "__main__":
    unittest.main()
