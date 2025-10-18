from pydantic import BaseModel
from typing import Any, Dict, Optional

class AskRequest(BaseModel):
    question: str
    vectorstore_id: str
    params: Optional[Dict[str, Any]] = None

class AskResponse(BaseModel):
    markdown: str
    sources: Optional[Any] = None
    meta: Optional[Dict[str, Any]] = None
