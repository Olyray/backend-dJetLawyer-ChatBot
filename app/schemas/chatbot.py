from pydantic import BaseModel
from typing import List, Optional

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    chat_id: Optional[str] = None
    message: str

class Source(BaseModel):
    url: str

class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    sources: List[Source] = []
    limit_reached: bool = False
