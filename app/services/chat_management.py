"""
Service module for chat management operations.
This module contains functions for handling chat creation, retrieval, and management.
"""

import uuid
from datetime import datetime
from fastapi import HTTPException
from typing import Tuple, List, Dict, Any, Optional, Union
from sqlalchemy.orm import Session

from app.schemas.chatbot import ChatResponse
from app.models.user import User
from app.schemas.chat import ChatCreate, MessageCreate
from app.services.chat import add_message, get_chat, create_chat, get_chat_messages
from app.services.anonymous_chat import get_anonymous_message_count, increment_anonymous_message_count, get_anonymous_chat_messages

def get_chat_id(chat_obj):
    """Extract the chat ID from either a dict or model object."""
    if isinstance(chat_obj, dict):
        return chat_obj["id"]
    else:
        return chat_obj.id

async def validate_anonymous_user(anonymous_session_id: str) -> Tuple[bool, Optional[ChatResponse]]:
    """
    Validates an anonymous user and checks if they've reached their message limit.
    
    Args:
        anonymous_session_id: The anonymous session ID
        
    Returns:
        Tuple of (is_limit_reached, error_response)
    """
    if not anonymous_session_id:
        raise HTTPException(status_code=400, detail="Anonymous session ID required")
    
    # Get message count from Redis
    message_count = await get_anonymous_message_count(anonymous_session_id)
    if message_count >= 5:
        # Return a success response with a limit_reached flag instead of an error
        return True, ChatResponse(
            chat_id="limit_reached",
            answer="Message limit reached. Please login to continue.",
            sources=[],
            limit_reached=True
        )
    
    # Increment message count
    await increment_anonymous_message_count(anonymous_session_id)
    return False, None

async def create_new_chat(
    current_user, 
    db: Session, 
    chat_request, 
    title_chain, 
    anonymous_session_id=None, 
    previous_messages=None
) -> Tuple[Any, List]:
    """
    Creates a new chat for either authenticated or anonymous users.
    
    Args:
        current_user: The current authenticated user or None
        db: Database session
        chat_request: The chat request object
        title_chain: The chain for generating chat titles
        anonymous_session_id: Optional anonymous session ID
        previous_messages: Optional previous messages from shared chat
        
    Returns:
        Tuple of (chat, messages)
    """
    if current_user:
        # For continuing from a shared chat with previous messages
        if previous_messages:
            chat_title = "Continued from shared chat"
            if len(previous_messages) > 0:
                chat_title = previous_messages[0].get('content', '')[:30] + "..."
            
            chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
            
            # Add previous messages to the new chat
            for msg in previous_messages:
                add_message(db, chat.id, MessageCreate(
                    role=msg.get('role', ''),
                    content=msg.get('content', '')
                ))
            
            messages = get_chat_messages(db, chat.id)
        else:
            chat_title = title_chain.invoke({"message": chat_request.message})
            chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
            messages = []
    else:
        # Create anonymous chat on Redis
        chat = {"id": uuid.uuid4()}
        
        # If we have previous messages from a shared chat, use them
        if previous_messages:
            messages = [
                {
                    "id": str(uuid.uuid4()),
                    "chat_id": str(chat["id"]),
                    "role": msg.get("role", ""),
                    "content": msg.get("content", ""),
                    "created_at": datetime.utcnow().isoformat()
                }
                for msg in previous_messages
            ]
        else:
            messages = []
    
    print("Created new chat with ID: ", get_chat_id(chat))
    return chat, messages

async def transfer_anonymous_chat(
    db: Session, 
    current_user: User, 
    chat_request, 
    anonymous_session_id: str, 
    title_chain
) -> Tuple[Any, List, bool]:
    """
    Transfers an anonymous chat to an authenticated user if needed.
    
    Args:
        db: Database session
        current_user: The authenticated user
        chat_request: The chat request
        anonymous_session_id: The anonymous session ID
        title_chain: The chain for generating chat titles
        
    Returns:
        Tuple of (chat, messages, chat_transfer_needed)
    """
    # First try to get the user's own chat
    chat = get_chat(db, chat_request.chat_id)
    
    # If the chat doesn't exist or doesn't belong to the user, 
    # check for anonymous chat to transfer
    if not chat or chat.user_id != current_user.id:
        # Check for anonymous chat with the same ID
        anon_messages = await get_anonymous_chat_messages(anonymous_session_id, str(chat_request.chat_id))
        print(f"Found {len(anon_messages)} anonymous messages to transfer")
        
        if anon_messages:
            # Create a new chat for the user with the original title
            chat_title = f"Transferred from anonymous chat"
            if len(anon_messages) > 0 and anon_messages[0]['role'] == 'human':
                chat_title = anon_messages[0]['content'][:30] + "..."
            
            chat = create_chat(db, current_user.id, ChatCreate(title=chat_title, id=chat_request.chat_id))
            print(f"Created new chat for transfer with ID: {chat.id}")
            
            # Add all anonymous messages to the new chat
            for msg in anon_messages:
                add_message(db, chat.id, MessageCreate(
                    role=msg['role'],
                    content=msg['content'],
                    sources=msg.get('sources')
                ))
            
            messages = get_chat_messages(db, chat.id)
            return chat, messages, True
        else:
            # No anonymous chat to transfer, create a new chat
            chat_title = title_chain.invoke({"message": chat_request.message})
            chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
            print(f"No anonymous chat found, created new chat with ID: {chat.id}")
            return chat, [], False
    else:
        # User's own chat exists
        messages = get_chat_messages(db, chat.id)
        return chat, messages, False

async def handle_existing_chat(
    current_user, 
    db: Session, 
    chat_request, 
    anonymous_session_id: str, 
    title_chain
) -> Tuple[Any, List, bool]:
    """
    Handles retrieving or creating a chat when a chat_id is provided.
    
    Args:
        current_user: The authenticated user or None
        db: Database session
        chat_request: The chat request object
        anonymous_session_id: Optional anonymous session ID
        title_chain: The chain for generating chat titles
        
    Returns:
        Tuple of (chat, messages, chat_transfer_needed)
    """
    # Check if we need to transfer an anonymous chat to a logged-in user
    if current_user and anonymous_session_id:
        return await transfer_anonymous_chat(db, current_user, chat_request, anonymous_session_id, title_chain)
    elif current_user:
        # Authenticated user, no anonymous session ID
        chat = get_chat(db, chat_request.chat_id)
        if not chat or chat.user_id != current_user.id:
            raise HTTPException(status_code=404, detail="Chat not found")
        messages = get_chat_messages(db, chat.id)
        return chat, messages, False
    else:
        # Anonymous user
        messages = await get_anonymous_chat_messages(anonymous_session_id, str(chat_request.chat_id))
        if not messages:
            # If no messages found for this chat ID, create a new chat
            chat = {"id": uuid.uuid4()}
            return chat, [], False
        else:
            chat = {"id": chat_request.chat_id}
            return chat, messages, False

async def handle_new_chat_session(
    current_user, 
    db: Session, 
    chat_request, 
    title_chain, 
    anonymous_session_id=None
) -> Tuple[Any, List, bool]:
    """
    Handles creating a new chat when no chat_id is provided.
    
    Args:
        current_user: The authenticated user or None
        db: Database session
        chat_request: The chat request
        title_chain: The chain for generating titles
        anonymous_session_id: Optional anonymous session ID
        
    Returns:
        Tuple of (chat, messages, chat_transfer_needed)
    """
    if current_user:
        # Create new chat for logged in users
        chat_title = title_chain.invoke({"message": chat_request.message})
        chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
        return chat, [], False
    else:
        # Create new chat ID for anonymous users
        chat = {"id": uuid.uuid4()}
        return chat, [], False 