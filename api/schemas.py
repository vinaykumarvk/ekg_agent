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


class VectorStoreUploadResponse(BaseModel):
    vector_store_id: str
    file_id: str
    filename: str
    size_bytes: int


class GoogleDriveIngestRequest(BaseModel):
    vector_store_name: str = Field(..., min_length=1, max_length=100)
    folder_id: str = Field(..., min_length=5)
    file_ids: List[str]


# -----------------------------------------------------------------------------
# Structured Input Schemas (New Endpoint)
# -----------------------------------------------------------------------------
class StructuredQuestionPayload(BaseModel):
    """Structured question payload for capabilities analysis"""
    system_prompt: str = Field(..., description="Custom system prompt for the analysis")
    requirement: str = Field(..., description="Main requirement description")
    bank_profile: Optional[Dict[str, Any]] = Field(None, description="Bank profile information")
    market_subrequirements: Optional[List[Dict[str, Any]]] = Field(None, description="List of market subrequirements")


class StructuredAnswerRequest(BaseModel):
    """Request schema for structured answer endpoint"""
    question_payload: StructuredQuestionPayload = Field(..., description="Structured question payload")
    domain: str = Field(default="wealth_management", description="Domain identifier")
    vectorstore_id: Optional[str] = Field(None, description="Vector store ID (uses domain default if not provided)")
    params: Optional[Dict[str, Any]] = Field(None, description="Additional parameters (mode, model, etc.)")


class StructuredAnswerResponse(BaseModel):
    """Response schema for structured answer endpoint"""
    response_id: str
    json_data: Optional[Dict[str, Any]] = Field(None, description="Structured JSON response")
    answer: Optional[str] = Field(None, description="Raw answer text (if JSON parsing failed)")
    sources: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None


# -----------------------------------------------------------------------------
# Web Search / Market Requirements Schemas
# -----------------------------------------------------------------------------
class WebSearchRequest(BaseModel):
    """Request schema for web search / market requirements endpoint"""
    requirement: str = Field(..., description="Requirement description to decompose")
    profile: Optional[Dict[str, Any]] = Field(None, description="Bank profile information")
    model: str = Field(default="gpt-4o", description="Model name to use")


class WebSearchResponse(BaseModel):
    """Response schema for web search endpoint"""
    response_id: str
    json_data: Optional[Dict[str, Any]] = Field(None, description="Market subrequirements JSON")
    answer: Optional[str] = Field(None, description="Raw answer text (if JSON parsing failed)")
    sources: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
