from sqlalchemy.orm import Session
from app.models.chat import Chat, Message
from app.schemas.chat import ChatCreate, MessageCreate
from app.schemas.chatbot import Source
from typing import Union
import uuid
import json

def create_chat(db: Session, user_id: uuid.UUID, chat: ChatCreate):
    db_chat = Chat(user_id=user_id, **chat.dict())
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    return db_chat

def get_user_chats(db: Session, user_id: uuid.UUID):
    return db.query(Chat).filter(Chat.user_id == user_id).all()
    
def get_chat(db: Session, chat_id: uuid.UUID):
    return db.query(Chat).filter(Chat.id == chat_id).first()

def add_message(db: Session, chat_id: uuid.UUID, message: Union[MessageCreate, dict]):
    if isinstance(message, dict):
        message = MessageCreate(**message)
    db_message = Message(chat_id=chat_id, **message.dict())
    db.add(db_message)
    db.commit()
    db.refresh(db_message)
    return db_message

def get_chat_messages(db: Session, chat_id: uuid.UUID):
    return db.query(Message).filter(Message.chat_id == chat_id).order_by(Message.created_at).all()