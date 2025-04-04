from pydantic import BaseModel
from typing import List, Optional, Dict, Any

class ChatMessage(BaseModel):
    role: str
    content: str

class Source(BaseModel):
    url: str

class AttachmentData(BaseModel):
    id: Optional[str] = None
    file_name: str
    file_type: str
    file_size: Optional[int] = None
    file_path: Optional[str] = None

class ChatRequest(BaseModel):
    message: str
    chat_id: Optional[str] = None
    previous_messages: Optional[List[Dict[str, Any]]] = None
    attachments: Optional[List[AttachmentData]] = None

class ChatResponse(BaseModel):
    chat_id: str
    answer: str
    sources: List[Source] = []
    limit_reached: bool = False
