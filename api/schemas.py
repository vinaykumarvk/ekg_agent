from pydantic import BaseModel
from typing import Any, Dict, Optional

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
