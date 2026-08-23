"""Optional live smoke test for Google Gemini API."""

import os
import pytest
from pydantic import BaseModel, Field
from app.providers.gemini import GeminiModelProvider

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")


class SmokeTestSchema(BaseModel):
    greeting: str = Field(..., description="A friendly greeting")
    status: str = Field(..., description="'OK' or 'ACTIVE'")


@pytest.mark.skipif(not GEMINI_API_KEY, reason="GEMINI_API_KEY is not configured in environment")
@pytest.mark.asyncio
async def test_live_gemini_structured_generation():
    """Live smoke test executing a minimal structured generation request against Gemini API."""
    provider = GeminiModelProvider(api_key=GEMINI_API_KEY, default_model="gemini-2.5-flash")

    result, token_metrics = await provider.generate_structured(
        prompt="Respond with a standard healthcheck greeting.",
        system_instruction="You are a healthcheck responder.",
        response_schema=SmokeTestSchema,
        temperature=0.0,
    )

    assert isinstance(result, SmokeTestSchema)
    assert result.status in ("OK", "ACTIVE")
    assert token_metrics.total_tokens > 0
