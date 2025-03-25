from sqlalchemy.orm import Session
from app.models.chat import Chat, Message
from app.schemas.chat import ChatCreate, MessageCreate, ShareChat
from app.schemas.chatbot import Source
from typing import Union, Optional
import uuid
import json

def create_chat(db: Session, user_id: uuid.UUID, chat: ChatCreate):
    # Create a dictionary from the chat data
    chat_data = chat.dict()
    
    # Extract id if present
    custom_id = chat_data.pop('id', None)
    
    # Create the chat with a custom ID if provided, otherwise let the default UUID generator handle it
    if custom_id:
        db_chat = Chat(id=custom_id, user_id=user_id, **chat_data)
    else:
        db_chat = Chat(user_id=user_id, **chat_data)
        
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

def share_chat(db: Session, chat_id: uuid.UUID, user_id: Optional[uuid.UUID] = None):
    """Mark a chat as shared and return it."""
    chat = db.query(Chat).filter(Chat.id == chat_id)
    
    # If user_id is provided, ensure the chat belongs to the user
    if user_id:
        chat = chat.filter(Chat.user_id == user_id)
    
    chat = chat.first()
    if not chat:
        return None
    
    chat.is_shared = True
    db.commit()
    db.refresh(chat)
    return chat

def get_shared_chat(db: Session, chat_id: uuid.UUID):
    """Get a chat that has been marked as shared."""
    return db.query(Chat).filter(Chat.id == chat_id, Chat.is_shared == True).first()

def save_anonymous_chat_to_db(db: Session, title: str, messages: list):
    """Save an anonymous chat to the database when it's shared."""
    # Create chat without a user_id
    db_chat = Chat(title=title, is_shared=True)
    db.add(db_chat)
    db.commit()
    db.refresh(db_chat)
    
    # Add all messages to the chat
    for msg in messages:
        db_message = Message(
            chat_id=db_chat.id, 
            role=msg["role"], 
            content=msg["content"],
            sources=msg.get("sources")
        )
        db.add(db_message)
    
    db.commit()
    return db_chat