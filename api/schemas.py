from __future__ import annotations

from pydantic import BaseModel, Field
from typing import Any, Dict, Optional, List

class AskRequest(BaseModel):
    question: str
    domain: str = "wealth_management"  # Default to existing domain for backward compatibility
    vectorstore_id: Optional[str] = None  # Now optional - can use domain default
    response_id: Optional[str] = None  # For conversational context
    conversation_id: Optional[str] = None  # Alternative conversation tracking
    params: Optional[Dict[str, Any]] = None

class AskResponse(BaseModel):
    response_id: str
    markdown: str
    sources: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None


class DomainInfo(BaseModel):
    """Information about an available domain"""
    domain_id: str
    name: str
    description: str
    kg_loaded: bool
    kg_nodes: int
    kg_edges: int
    default_vectorstore_id: Optional[str]


class VectorStoreUploadResponse(BaseModel):
    vector_store_id: str
    file_id: str
    filename: str
    size_bytes: int


class GoogleDriveIngestRequest(BaseModel):
    vector_store_name: str = Field(..., min_length=1, max_length=100)
    folder_id: str = Field(..., min_length=5)
    file_ids: List[str]
