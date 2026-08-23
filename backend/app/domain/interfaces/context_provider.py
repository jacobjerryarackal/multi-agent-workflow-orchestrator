"""Abstract interface protocol for Context Providers (MemoryOps AI integration)."""

from typing import Any, Dict, List, Protocol


class ContextProvider(Protocol):
    """Protocol for fetching contextual memory or tenant context for workflows."""

    async def get_context(
        self,
        query: str,
        namespace: str,
        limit: int = 5,
        metadata_filter: Dict[str, Any] | None = None,
    ) -> List[Dict[str, Any]]:
        """Retrieves relevant context items matching the query and namespace."""
        ...

    async def record_context(
        self,
        namespace: str,
        content: str,
        metadata: Dict[str, Any] | None = None,
    ) -> str:
        """Persists a new contextual memory item, returning its unique record ID."""
        ...
