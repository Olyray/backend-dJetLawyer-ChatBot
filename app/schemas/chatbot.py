from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str
    previous_messages: Optional[List[Dict[str, Any]]] = None

class Source(BaseModel):
    url: str

class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    sources: List[Source] = []
    limit_reached: bool = False
