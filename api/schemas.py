from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Any, Dict, Optional, List, Literal

class AskRequest(BaseModel):
    """Request schema for simple string-based questions (backward compatible)"""
    question: str = Field(..., description="Question string")
    domain: str = Field(default="wealth_management", description="Domain identifier")
    vectorstore_id: Optional[str] = Field(None, description="Vector store ID (uses domain default if not provided)")
    response_id: Optional[str] = Field(None, description="Response ID for conversational context")
    conversation_id: Optional[str] = Field(None, description="Conversation ID for threading")
    params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters (mode, model, etc.)")
    output_format: Literal["markdown", "json"] = Field(default="markdown", description="Output format")

class AskResponse(BaseModel):
    response_id: str
    markdown: Optional[str] = None  # Markdown output (for backward compatibility)
    json_data: Optional[Dict[str, Any]] = None  # JSON output (for structured responses)
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
    kg_vectorstore_id: Optional[str] = None


class VectorStoreUploadResponse(BaseModel):
    vector_store_id: str
    file_id: str
    filename: str
    size_bytes: int


class GoogleDriveIngestRequest(BaseModel):
    vector_store_name: str = Field(..., min_length=1, max_length=100)
    folder_id: str = Field(..., min_length=5)
    file_ids: List[str]


