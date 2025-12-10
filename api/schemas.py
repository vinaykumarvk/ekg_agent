from pydantic import BaseModel, model_validator
from typing import Any, Dict, Optional, Literal

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
        if not self.question and not self.question_payload:
            raise ValueError("Either 'question' or 'question_payload' must be provided")
        
        # Auto-set to JSON if structured payload is used
        if self.question_payload and self.output_format != "json":
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
