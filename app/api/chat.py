from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.core.deps import get_db, get_current_user
from app.schemas.chat import ChatCreate, Chat, MessageCreate, Message
from app.services.chat import create_chat, get_user_chats, get_chat, add_message, get_chat_messages
from app.models.user import User
import uuid

router = APIRouter()

@router.post("/chats", response_model=Chat)
def create_new_chat(chat: ChatCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return create_chat(db, current_user.id, chat)

@router.get("/chats", response_model=List[Chat])
def read_user_chats(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    return get_user_chats(db, current_user.id)

@router.get("/chats/{chat_id}", response_model=Chat)
def read_chat(chat_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    chat = get_chat(db, chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return chat

@router.post("/chats/{chat_id}/messages", response_model=Message)
def create_message(chat_id: uuid.UUID, message: MessageCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    chat = get_chat(db, chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return add_message(db, chat_id, message)

@router.get("/chats/{chat_id}/messages", response_model=List[Message])
def read_chat_messages(chat_id: uuid.UUID, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    chat = get_chat(db, chat_id)
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Chat not found")
    return get_chat_messages(db, chat_id)
