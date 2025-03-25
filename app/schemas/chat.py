from pydantic import BaseModel, Json
from datetime import datetime
from typing import List, Optional, Dict
import uuid


class Source(BaseModel):
    url: str

class MessageBase(BaseModel):
    role: str
    content: str
    sources: Optional[List] = None 

class MessageCreate(MessageBase):
    pass

class Message(MessageBase):
    id: uuid.UUID
    chat_id: uuid.UUID
    created_at: datetime

    class Config:
        from_attributes = True

class ChatBase(BaseModel):
    title: str

class ChatCreate(ChatBase):
    id: Optional[uuid.UUID] = None

class ShareChat(BaseModel):
    is_shared: bool = True

class Chat(ChatBase):
    id: uuid.UUID
    user_id: uuid.UUID
    created_at: datetime
    updated_at: datetime
    is_shared: bool = False
    messages: List[Message] = []

    class Config:
        from_attributes = True

class PublicChat(BaseModel):
    id: uuid.UUID
    title: str
    created_at: datetime
    messages: List[Message] = []

    class Config:
        from_attributes = True
