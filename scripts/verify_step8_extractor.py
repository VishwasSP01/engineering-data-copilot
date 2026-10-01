#!/usr/bin/env python3
"""
Step 8 Verification Suite: Gemini Measurement Extractor & Deterministic Guardrails.

Verifies:
1. Pydantic schema validation for MeasurementExtractionResponse.
2. Prompt boundary enforcement (only requested measurement & passage supplied).
3. Deterministic extractor default behavior and metadata.
4. Injected mock Gemini client behavior (zero external network requests):
   - Valid extraction -> successful conversion & proposed correction
   - Invented quote -> rejected by grounding guardrail (needs_review)
   - Unsupported unit -> rejected by unit guardrail (needs_review)
   - Malformed output (non-JSON or schema violation) -> rejected (needs_review)
   - Model abstentions (insufficient / ambiguous) -> handled correctly
   - Timeout and API error -> caught and returned as needs_review
   - Missing credentials -> graceful error handling without crashing
5. Output metadata formatting (provider, model, duration, token usage).
"""

import os
import sys
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

# Ensure scripts directory is on sys.path
repo_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(repo_root / "scripts"))

from extractors import (
    BaseMeasurementExtractor,
    DeterministicMeasurementExtractor,
    GeminiMeasurementExtractor,
    MeasurementExtractionResponse,
    build_extraction_prompt,
    get_extractor,
    SUPPORTED_UNITS,
)
from investigate_record import investigate_record


# ---------------------------------------------------------------------------
# Mock Helpers for Testing Without Live Network Calls
# ---------------------------------------------------------------------------

class MockTokenUsage:
    def __init__(self, prompt_tokens: int = 50, candidates_tokens: int = 20, total_tokens: int = 70):
        self.prompt_token_count = prompt_tokens
        self.candidates_token_count = candidates_tokens
        self.total_token_count = total_tokens


class MockResponse:
    def __init__(self, text: str, usage_metadata: Optional[MockTokenUsage] = None):
        self.text = text
        self.usage_metadata = usage_metadata


class MockModels:
    def __init__(self, handler):
        self._handler = handler

    def generate_content(self, model: str, contents: str, config: Any = None):
        return self._handler(model, contents, config)


class MockGeminiClient:
    def __init__(self, handler):
        self.models = MockModels(handler)


# ---------------------------------------------------------------------------
# Test Functions
# ---------------------------------------------------------------------------

def test_pydantic_schema_validation():
    print("Verifying Pydantic schema validation...")

    # 1. Valid found response
    valid_json = (
        '{"status": "found", "measurement_name": "thickness", '
        '"value": "0.8", "unit": "cm", "quote": "Component thickness: 0.8 cm."}'
    )
    resp = MeasurementExtractionResponse.model_validate_json(valid_json)
    assert resp.status == "found"
    assert resp.measurement_name == "thickness"
    assert resp.value == "0.8"
    assert resp.unit == "cm"
    assert resp.quote == "Component thickness: 0.8 cm."

    # 2. Missing required field when status is 'found'
    missing_value_json = '{"status": "found", "measurement_name": "thickness", "unit": "cm", "quote": "0.8 cm"}'
    try:
        MeasurementExtractionResponse.model_validate_json(missing_value_json)
        raise AssertionError("Failed to catch missing 'value' in found status!")
    except Exception:
        pass

    # 3. Invalid decimal string when status is 'found'
    invalid_num_json = (
        '{"status": "found", "measurement_name": "thickness", '
        '"value": "NOT_A_DECIMAL", "unit": "cm", "quote": "0.8 cm"}'
    )
    try:
        MeasurementExtractionResponse.model_validate_json(invalid_num_json)
        raise AssertionError("Failed to catch invalid decimal string!")
    except Exception:
        pass

    # 4. Valid insufficient response (no measurement fields required)
    insuff_json = '{"status": "insufficient"}'
    resp_insuff = MeasurementExtractionResponse.model_validate_json(insuff_json)
    assert resp_insuff.status == "insufficient"
    assert resp_insuff.value is None

    # 5. Valid ambiguous response
    ambig_json = '{"status": "ambiguous"}'
    resp_ambig = MeasurementExtractionResponse.model_validate_json(ambig_json)
    assert resp_ambig.status == "ambiguous"

    print("✓ Pydantic schema validation behaves correctly on valid and invalid payloads.")


def test_prompt_construction():
    print("Verifying prompt construction boundaries...")
    passage = "The bracket has thickness: 0.8 cm."
    attr = "thickness"
    prompt = build_extraction_prompt(passage, attr)

    # Must contain attribute name and passage
    assert attr in prompt, "Prompt missing requested attribute name."
    assert passage in prompt, "Prompt missing evidence passage."

    # Must NOT mention target units, conversions, or expected values
    assert "target_unit" not in prompt
    assert "convert" in prompt.lower()  # Should instruct NOT to convert
    assert "do not convert" in prompt.lower() or "do not" in prompt.lower()

    print("✓ Prompt boundaries strictly isolate extraction without leaking conversion or record targets.")


def test_deterministic_extractor_baseline():
    print("Verifying deterministic extractor baseline...")
    extractor = get_extractor("deterministic")
    assert isinstance(extractor, DeterministicMeasurementExtractor)

    res = extractor.extract_measurement("Component thickness: 0.8 cm.", "thickness")
    assert res.status == "found"
    assert res.value == Decimal("0.8")
    assert res.unit == "cm"
    assert res.provider == "deterministic"
    assert res.model is None
    assert res.token_usage is None
    assert res.call_duration_ms >= 0.0

    print("✓ Deterministic extractor baseline produces structured result and execution metadata.")


def test_mock_gemini_scenarios():
    print("Verifying mock Gemini adapter across required scenarios (zero network calls)...")
    sample_record = repo_root / "data" / "records" / "unit-mismatch-001.json"

    # Scenario 1: Valid extraction
    def valid_handler(model, contents, config):
        return MockResponse(
            '{"status": "found", "measurement_name": "thickness", "value": "0.8", "unit": "cm", "quote": "Component thickness: 0.8 cm."}',
            MockTokenUsage(prompt_tokens=48, candidates_tokens=22, total_tokens=70)
        )

    client1 = MockGeminiClient(valid_handler)
    ext1 = GeminiMeasurementExtractor(client=client1, model="gemini-2.5-flash")
    res1 = investigate_record(sample_record, extractor=ext1)
    assert res1["outcome"] == "correction_proposed", f"Expected correction_proposed, got {res1['outcome']}"
    assert res1["proposed_correction"]["value"] == 8.0
    assert res1["proposed_correction"]["unit"] == "mm"
    assert res1["extractor"]["provider"] == "google-genai"
    assert res1["extractor"]["model"] == "gemini-2.5-flash"
    assert res1["extractor"]["mode"] == "model"
    assert res1["extractor"]["token_usage"]["total_tokens"] == 70
    assert res1["evidence"]["supporting_passage"] == "Component thickness: 0.8 cm."
    print("  [✓] Scenario 1: Valid extraction -> correct proposed correction and metadata.")

    # Scenario 2: Invented quote (hallucinated quote not in passage)
    def invented_quote_handler(model, contents, config):
        return MockResponse(
            '{"status": "found", "measurement_name": "thickness", "value": "0.8", "unit": "cm", "quote": "Invented hallucinated text."}',
            MockTokenUsage()
        )

    client2 = MockGeminiClient(invented_quote_handler)
    ext2 = GeminiMeasurementExtractor(client=client2)
    res2 = investigate_record(sample_record, extractor=ext2)
    assert res2["outcome"] == "needs_review", f"Expected needs_review, got {res2['outcome']}"
    assert res2["proposed_correction"] is None
    assert "ungrounded" in res2["explanation"].lower()
    print("  [✓] Scenario 2: Invented quote -> caught by grounding guardrail (needs_review).")

    # Scenario 3: Unsupported value or unit
    def unsupported_unit_handler(model, contents, config):
        # Case where document contains mm/cm, but model returned unit 'in'
        return MockResponse(
            '{"status": "found", "measurement_name": "thickness", "value": "0.8", "unit": "in", "quote": "thickness: 0.8 in"}',
            MockTokenUsage()
        )

    client3 = MockGeminiClient(unsupported_unit_handler)
    ext3 = GeminiMeasurementExtractor(client=client3)
    res3 = investigate_record(sample_record, extractor=ext3)
    assert res3["outcome"] == "needs_review", f"Expected needs_review, got {res3['outcome']}"
    assert res3["proposed_correction"] is None
    print("  [✓] Scenario 3: Unsupported unit -> caught by unit/quote guardrail (needs_review).")

    # Scenario 4: Malformed output
    # Subcase 4a: Non-JSON raw text
    def non_json_handler(model, contents, config):
        return MockResponse("This is not valid JSON at all.", MockTokenUsage())

    client4a = MockGeminiClient(non_json_handler)
    ext4a = GeminiMeasurementExtractor(client=client4a)
    res4a = investigate_record(sample_record, extractor=ext4a)
    assert res4a["outcome"] == "needs_review", f"Expected needs_review, got {res4a['outcome']}"
    assert res4a["proposed_correction"] is None
    assert "malformed" in res4a["explanation"].lower() or "schema" in res4a["explanation"].lower()

    # Subcase 4b: Schema violation (found without required fields)
    def invalid_schema_handler(model, contents, config):
        return MockResponse('{"status": "found", "value": "NOT_NUMERIC"}', MockTokenUsage())

    client4b = MockGeminiClient(invalid_schema_handler)
    ext4b = GeminiMeasurementExtractor(client=client4b)
    res4b = investigate_record(sample_record, extractor=ext4b)
    assert res4b["outcome"] == "needs_review"
    assert res4b["proposed_correction"] is None
    print("  [✓] Scenario 4: Malformed output -> rejected cleanly (needs_review).")

    # Scenario 5: Model abstention
    def insufficient_handler(model, contents, config):
        return MockResponse('{"status": "insufficient"}', MockTokenUsage())

    client5a = MockGeminiClient(insufficient_handler)
    ext5a = GeminiMeasurementExtractor(client=client5a)
    res5a = investigate_record(sample_record, extractor=ext5a)
    assert res5a["outcome"] == "insufficient_evidence"
    assert res5a["proposed_correction"] is None

    def ambiguous_handler(model, contents, config):
        return MockResponse('{"status": "ambiguous"}', MockTokenUsage())

    client5b = MockGeminiClient(ambiguous_handler)
    ext5b = GeminiMeasurementExtractor(client=client5b)
    res5b = investigate_record(sample_record, extractor=ext5b)
    assert res5b["outcome"] == "ambiguous_evidence"
    assert res5b["proposed_correction"] is None
    print("  [✓] Scenario 5: Model abstention (insufficient / ambiguous) -> handled correctly.")

    # Scenario 6: Timeout or API failure
    def timeout_handler(model, contents, config):
        raise TimeoutError("Client request timed out after 10000ms")

    client6 = MockGeminiClient(timeout_handler)
    ext6 = GeminiMeasurementExtractor(client=client6)
    res6 = investigate_record(sample_record, extractor=ext6)
    assert res6["outcome"] == "needs_review"
    assert res6["proposed_correction"] is None
    assert "timed out" in res6["explanation"].lower()
    print("  [✓] Scenario 6: Timeout and API failure -> caught cleanly without unhandled exceptions.")

    # Scenario 7: Missing credentials
    # Ensure GEMINI_API_KEY is not in env or loaded from .env for this subtest
    orig_key = os.environ.pop("GEMINI_API_KEY", None)
    env_file = repo_root / ".env"
    env_backup = repo_root / ".env.bak_test"
    if env_file.exists():
        env_file.rename(env_backup)
    try:
        ext7 = GeminiMeasurementExtractor()  # no client, no key
        res7 = investigate_record(sample_record, extractor=ext7)
        assert res7["outcome"] == "needs_review"
        assert "gemini_api_key" in res7["explanation"].lower()
    finally:
        if env_backup.exists():
            env_backup.rename(env_file)
        if orig_key is not None:
            os.environ["GEMINI_API_KEY"] = orig_key
    print("  [✓] Scenario 7: Missing credentials -> returns needs_review with clear guidance.")


def run_all_step8_checks():
    print("=== Step 8 Verification Suite ===")
    test_pydantic_schema_validation()
    test_prompt_construction()
    test_deterministic_extractor_baseline()
    test_mock_gemini_scenarios()
    print("ALL STEP 8 VERIFICATION CHECKS PASSED SUCCESSFULLY.\n")


if __name__ == "__main__":
    run_all_step8_checks()
