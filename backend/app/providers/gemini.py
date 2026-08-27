"""Google Gemini ModelProvider implementation adhering to the domain ModelProvider protocol."""

import json
import time
from typing import Any, Optional, Tuple, Type
from pydantic import BaseModel, ValidationError

try:
    from google import genai
    from google.genai import types
    from google.genai.errors import APIError
    GENAI_AVAILABLE = True
except ImportError:
    genai = None
    types = None
    APIError = Exception  # type: ignore
    GENAI_AVAILABLE = False

from ..core.config import settings
from ..core.exceptions import OrchestratorException, SchemaValidationError
from ..domain.interfaces.model_provider import ModelProvider
from ..domain.models.agent import TokenUsageMetrics
from ..domain.models.failure import FailureCategory


class GeminiProviderError(OrchestratorException):
    """Normalized provider-level error originating from the Gemini API."""
    def __init__(self, message: str, category: FailureCategory = FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE):
        super().__init__(message)
        self.category = category


class GeminiModelProvider(ModelProvider):
    """
    Concrete implementation of ModelProvider backed by Google Gemini GenAI SDK.
    Handles API credentials, structured schema enforcement, usage normalization, and error translation.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        default_model: str = "gemini-2.5-flash",
    ):
        self.api_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.default_model = default_model
        self._client: Any = None

        if self.api_key and GENAI_AVAILABLE and genai is not None:
            self._client = genai.Client(api_key=self.api_key)

    def _ensure_client(self) -> Any:
        if not GENAI_AVAILABLE or genai is None or types is None:
            raise GeminiProviderError(
                "google-genai SDK is not installed.",
                category=FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE,
            )
        if not self._client:
            if not self.api_key:
                raise GeminiProviderError(
                    "GEMINI_API_KEY is not configured.",
                    category=FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE,
                )
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> Tuple[BaseModel, TokenUsageMetrics]:
        """
        Invokes Gemini with structured response_schema, parses JSON, and returns a typed Pydantic instance.
        """
        client = self._ensure_client()
        assert types is not None

        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
            response_mime_type="application/json",
            response_schema=response_schema,
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.default_model,
                contents=prompt,
                config=config,
            )
        except APIError as exc:
            code = getattr(exc, "code", 500)
            if code == 429:
                category = FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE
                raise GeminiProviderError(f"Gemini rate limit exceeded: {exc}", category=category) from exc
            elif code in (500, 503):
                category = FailureCategory.INFRASTRUCTURE_PROVIDER_FAILURE
                raise GeminiProviderError(f"Gemini service unavailable ({code}): {exc}", category=category) from exc
            else:
                raise GeminiProviderError(f"Gemini API error ({code}): {exc}") from exc
        except Exception as exc:
            raise GeminiProviderError(f"Unexpected model execution failure: {exc}") from exc

        # Extract usage metrics
        token_metrics = self._extract_token_usage(response)

        raw_text = response.text or ""
        if not raw_text.strip():
            raise GeminiProviderError(
                "Gemini returned empty structured output.",
                category=FailureCategory.CONTRACT_VALIDATION_FAILURE,
            )

        try:
            parsed_data = json.loads(raw_text)
            structured_instance = response_schema.model_validate(parsed_data)
            return structured_instance, token_metrics
        except (json.JSONDecodeError, ValidationError) as exc:
            raise SchemaValidationError(
                f"Failed to validate Gemini response against schema '{response_schema.__name__}': {exc}"
            ) from exc

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> Tuple[str, TokenUsageMetrics]:
        """
        Invokes Gemini for freeform text generation.
        """
        client = self._ensure_client()
        assert types is not None
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            temperature=temperature,
        )

        try:
            response = await client.aio.models.generate_content(
                model=self.default_model,
                contents=prompt,
                config=config,
            )
        except Exception as exc:
            raise GeminiProviderError(f"Gemini text generation failed: {exc}") from exc

        token_metrics = self._extract_token_usage(response)
        return response.text or "", token_metrics

    def _extract_token_usage(self, response: Any) -> TokenUsageMetrics:
        """Normalizes token metadata from Gemini response."""
        usage = getattr(response, "usage_metadata", None)
        if not usage:
            return TokenUsageMetrics()

        prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
        completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
        total_tokens = getattr(usage, "total_token_count", prompt_tokens + completion_tokens) or 0

        return TokenUsageMetrics(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
