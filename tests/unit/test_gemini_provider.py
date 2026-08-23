"""Unit tests for GeminiModelProvider error translation and usage extraction."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from pydantic import BaseModel
from app.providers.gemini import GeminiModelProvider, GeminiProviderError
from app.core.exceptions import SchemaValidationError


class SampleResponseSchema(BaseModel):
    key: str
    score: float


def test_gemini_provider_init():
    provider = GeminiModelProvider(api_key="test_dummy_key", default_model="gemini-2.5-flash")
    assert provider.api_key == "test_dummy_key"
    assert provider.default_model == "gemini-2.5-flash"


def test_gemini_provider_missing_key_raises():
    provider = GeminiModelProvider(api_key="")
    with pytest.raises(GeminiProviderError, match="GEMINI_API_KEY is not configured"):
        provider._ensure_client()


def test_token_usage_extraction():
    provider = GeminiModelProvider(api_key="dummy")
    
    mock_response = MagicMock()
    mock_response.usage_metadata.prompt_token_count = 120
    mock_response.usage_metadata.candidates_token_count = 80
    mock_response.usage_metadata.total_token_count = 200

    metrics = provider._extract_token_usage(mock_response)
    assert metrics.prompt_tokens == 120
    assert metrics.completion_tokens == 80
    assert metrics.total_tokens == 200


def test_token_usage_extraction_empty():
    provider = GeminiModelProvider(api_key="dummy")
    mock_response = MagicMock()
    mock_response.usage_metadata = None

    metrics = provider._extract_token_usage(mock_response)
    assert metrics.prompt_tokens == 0
    assert metrics.completion_tokens == 0
    assert metrics.total_tokens == 0
