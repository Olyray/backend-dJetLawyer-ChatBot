__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import os
import uuid
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from app.schemas.chatbot import ChatRequest, ChatResponse
from app.schemas.chat import PublicChat
from app.utils.model_init import initialize_models
from app.core.deps import get_db, get_optional_current_user
from app.models.user import User
from app.services.chat import save_anonymous_chat_to_db
from langchain_core.prompts import PromptTemplate
from langchain_core.runnables import RunnableSequence
from langchain_google_genai import ChatGoogleGenerativeAI
from typing import Optional
from app.services.anonymous_chat import get_anonymous_chat_messages

# Import the new service modules
from app.services.chat_management import (
    validate_anonymous_user,
    create_new_chat,
    handle_existing_chat,
    handle_new_chat_session
)
from app.services.chat_processing import process_chat

router = APIRouter()

# Initialize the RAG chain
rag_chain = initialize_models()
llm = ChatGoogleGenerativeAI(
    google_api_key=os.getenv('GEMINI_API_KEY'),
    model='gemini-2.0-flash',
    temperature=0.5
)

# Define the title template and chain
title_template = PromptTemplate.from_template("Summarize the following message in 5 words or less to create a chat title: {message}")

# Extract the title from the input message
title_chain = RunnableSequence(
    title_template | llm | (lambda x: x.content.strip())
)

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    chat_request: ChatRequest, 
    db: Session = Depends(get_db), 
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    try:
        # Get anonymous session ID from request headers
        anonymous_session_id = request.headers.get('x-anonymous-session-id')
        
        # Validate anonymous user and check message limits
        if not current_user:
            limit_reached, error_response = await validate_anonymous_user(anonymous_session_id)
            if limit_reached:
                return error_response
        
        # Get the previous messages from the shared chat
        previous_messages = getattr(chat_request, 'previous_messages', None)

        # Process the chat based on whether a chat_id is provided
        if chat_request.chat_id:
            try:
                chat_request.chat_id = uuid.UUID(chat_request.chat_id)
                # Handle existing chat (retrieve or transfer)
                chat, messages, _ = await handle_existing_chat(
                    current_user, db, chat_request, anonymous_session_id, title_chain
                )
            except ValueError:
                # If chat_id is not a valid UUID, create a new chat
                chat, messages = await create_new_chat(
                    current_user, db, chat_request, title_chain, 
                    anonymous_session_id, previous_messages
                )
                
                # Process the chat immediately for new chats with invalid UUIDs
                return await process_chat(
                    current_user, anonymous_session_id, chat, messages, 
                    chat_request.message, title_chain, db, rag_chain,
                    attachments=chat_request.attachments
                )
        else:
            # No chat ID provided, create a new chat
            chat, messages, _ = await handle_new_chat_session(
                current_user, db, chat_request, title_chain, anonymous_session_id
            )
        
        # Process the chat and return response
        return await process_chat(
            current_user, anonymous_session_id, chat, messages, 
            chat_request.message, title_chain, db, rag_chain,
            attachments=chat_request.attachments
        )
        
    except Exception as e:
        print(f"Status Code: 500, Detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/share-anonymous-chat", response_model=PublicChat)
async def share_anonymous_chat(
    request: Request,
    chat_data: dict,
    db: Session = Depends(get_db)
):
    """
    Share an anonymous chat by saving it to the database and making it publicly accessible.
    
    This takes the messages from Redis and saves them permanently in the database.
    """
    session_id = chat_data.get("session_id")
    chat_id = chat_data.get("chat_id")
    title = chat_data.get("title", "Anonymous Chat")
    
    if not session_id or not chat_id:
        raise HTTPException(status_code=400, detail="Session ID and Chat ID are required")
    
    # Get the messages from Redis
    messages = await get_anonymous_chat_messages(session_id, chat_id)
    
    if not messages:
        raise HTTPException(status_code=404, detail="Chat not found")
    
    # Save the chat to the database
    db_chat = save_anonymous_chat_to_db(db, title, messages)
    
    return db_chat