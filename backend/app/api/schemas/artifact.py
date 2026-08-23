"""API response schemas for Artifact metadata and content retrieval."""

from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel


class ArtifactResponse(BaseModel):
    id: str
    workflow_execution_id: str
    task_key: Optional[str] = None
    task_execution_id: Optional[str] = None
    artifact_name: str
    artifact_type: str
    content_hash: str
    size_bytes: int
    storage_uri: Optional[str] = None
    metadata: Dict[str, Any]
    created_at: datetime


class ArtifactContentResponse(BaseModel):
    artifact_id: str
    artifact_name: str
    artifact_type: str
    content_hash: str
    verified: bool
    data: Any


class ArtifactListResponse(BaseModel):
    items: List[ArtifactResponse]
    total_count: int
