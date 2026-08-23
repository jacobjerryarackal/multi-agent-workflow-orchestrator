"""Abstract interface protocol for LLM Model Providers (Gemini gateway)."""

from typing import Dict, Protocol, Tuple, Type
from pydantic import BaseModel
from ..models.agent import TokenUsageMetrics


class ModelProvider(Protocol):
    """Protocol defining the interface for LLM completion and structured generation."""

    async def generate_structured(
        self,
        prompt: str,
        system_instruction: str,
        response_schema: Type[BaseModel],
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> Tuple[BaseModel, TokenUsageMetrics]:
        """Generates structured output strictly conforming to the provided Pydantic response schema."""
        ...

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str,
        temperature: float = 0.2,
        timeout_seconds: float = 60.0,
    ) -> Tuple[str, TokenUsageMetrics]:
        """Generates freeform text completion."""
        ...
