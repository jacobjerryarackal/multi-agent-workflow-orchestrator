"""Domain models for stored artifacts, intermediate data assets, and checksums."""

from datetime import datetime
from enum import Enum
import hashlib
import json
from typing import Any, Dict, Optional
import uuid
from pydantic import BaseModel, Field


class ArtifactType(str, Enum):
    """Supported artifact data categories."""
    JSON = "json"
    MARKDOWN = "markdown"
    TEXT = "text"
    CSV = "csv"
    BINARY = "binary"


class Artifact(BaseModel):
    """Durable artifact representation produced by workflow tasks."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    workflow_execution_id: str
    task_key: str
    name: str = Field(..., description="Unique name/identifier for the artifact within the task")
    artifact_type: ArtifactType = ArtifactType.JSON
    content: str = Field(..., description="Raw text, JSON string, or serialized URI reference")
    checksum_sha256: str = Field(..., description="Cryptographic SHA-256 integrity hash")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @classmethod
    def create_from_data(
        cls,
        workflow_execution_id: str,
        task_key: str,
        name: str,
        data: Any,
        artifact_type: ArtifactType = ArtifactType.JSON,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "Artifact":
        """Factory method computing the SHA-256 checksum automatically."""
        if artifact_type == ArtifactType.JSON and not isinstance(data, str):
            content_str = json.dumps(data, sort_keys=True)
        else:
            content_str = str(data)

        checksum = hashlib.sha256(content_str.encode("utf-8")).hexdigest()

        return cls(
            workflow_execution_id=workflow_execution_id,
            task_key=task_key,
            name=name,
            artifact_type=artifact_type,
            content=content_str,
            checksum_sha256=checksum,
            metadata=metadata or {},
        )

    def verify_integrity(self) -> bool:
        """Verifies that the content matches its cryptographic SHA-256 hash."""
        computed = hashlib.sha256(self.content.encode("utf-8")).hexdigest()
        return computed == self.checksum_sha256
