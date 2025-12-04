from __future__ import annotations

from pydantic import BaseModel, Field, model_validator
from typing import Any, Dict, Optional, List, Literal

class AskRequest(BaseModel):
    # Support both simple string question and structured payload
    question: Optional[str] = None  # Simple question string (backward compatible)
    question_payload: Optional[Dict[str, Any]] = None  # Structured input with system_prompt, requirement, etc.
    domain: str = "wealth_management"  # Default to existing domain for backward compatibility
    vectorstore_id: Optional[str] = None  # Now optional - can use domain default
    response_id: Optional[str] = None  # For conversational context
    conversation_id: Optional[str] = None  # Alternative conversation tracking
    params: Optional[Dict[str, Any]] = None
    output_format: Literal["markdown", "json"] = "markdown"  # Output format control
    
    @model_validator(mode='after')
    def validate_question_or_payload(self):
        """Ensure at least one of question or question_payload is provided"""
        # Check if question is provided and not empty
        has_question = self.question is not None and str(self.question).strip() != ""
        
        # Check if question_payload is provided and not empty
        has_payload = (
            self.question_payload is not None and 
            isinstance(self.question_payload, dict) and 
            len(self.question_payload) > 0
        )
        
        if not has_question and not has_payload:
            raise ValueError(
                "Either 'question' (string) or 'question_payload' (dict) must be provided. "
                "question_payload should contain: system_prompt, requirement, bank_profile, market_subrequirements"
            )
        
        # Auto-set to JSON if structured payload is used
        if has_payload and self.output_format != "json":
            self.output_format = "json"
        
        return self

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
