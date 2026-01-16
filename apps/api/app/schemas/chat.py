from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any

class AskRequest(BaseModel):
    question: str = Field(..., min_length=2)
    session_id: Optional[str] = None
    top_k: int = 8

class AskResponse(BaseModel):
    session_id: str
    answer: str
    sources: List[Dict[str, Any]]