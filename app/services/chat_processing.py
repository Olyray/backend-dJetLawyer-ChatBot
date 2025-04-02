"""
Service module for processing chat messages through the language model.
This module contains functions for managing chat history, token counting, and generating responses.
"""

import uuid
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.schemas.chatbot import ChatResponse
from app.schemas.chat import MessageCreate
from app.schemas.usage import TokenUsageCreate
from app.models.token_usage import TokenUsage
from app.services.chat import add_message
from app.services.anonymous_chat import save_anonymous_chat_messages
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

def get_chat_id(chat_obj):
    """Extract the chat ID from either a dict or model object."""
    if isinstance(chat_obj, dict):
        return chat_obj["id"]
    else:
        return chat_obj.id

def count_tokens(text: str) -> int:
    """Count the tokens in the message."""
    from tiktoken import encoding_for_model
    enc = encoding_for_model("gpt-4")
    return len(enc.encode(text))

def summarize_chat_history(chat_history, llm):
    """
    Summarize the chat history when it exceeds token limits.
    
    Args:
        chat_history: The chat history to summarize
        llm: The language model to use for summarization
        
    Returns:
        A summary of the chat history
    """
    from langchain_core.prompts import PromptTemplate
    
    summary_prompt = PromptTemplate.from_template(
        "Summarize the following conversation in 200 words or less: {chat_history}"
    )
    summary_chain = summary_prompt | llm | (lambda x: x.content.strip())
    
    # Format the chat history, handling both object and dict messages
    formatted_history = []
    for msg in chat_history:
        role = msg['role'] if isinstance(msg, dict) else msg.role
        content = msg['content'] if isinstance(msg, dict) else msg.content
        formatted_history.append(f"{role}: {content}")
    
    return summary_chain.invoke({"chat_history": "\n".join(formatted_history)})

def prepare_chat_history(messages: List) -> List:
    """
    Convert chat history to the format expected by the language model chain.
    
    Args:
        messages: List of message objects or dictionaries
        
    Returns:
        Formatted chat history for the language model
    """
    total_tokens = sum(count_tokens(msg['content'] if isinstance(msg, dict) else msg.content) for msg in messages)

    # If total tokens exceed 1500, summarize the chat history
    if total_tokens > 1500:
        from langchain_google_genai import ChatGoogleGenerativeAI
        import os
        
        # Initialize LLM for summarization if needed
        llm = ChatGoogleGenerativeAI(
            google_api_key=os.getenv('GEMINI_API_KEY'),
            model='gemini-2.0-flash',
            temperature=0.5
        )
        
        summary = summarize_chat_history(messages, llm)
        chat_history = [HumanMessage(content=f"Chat history summary: {summary}")]
    else:
        # Convert chat history to the format expected by the chain
        chat_history = [
            HumanMessage(content=msg['content'] if isinstance(msg, dict) else msg.content) 
            if (isinstance(msg, dict) and msg['role'] == "human") or (hasattr(msg, 'role') and msg.role == "human")
            else AIMessage(content=msg['content'] if isinstance(msg, dict) else msg.content) 
            if (isinstance(msg, dict) and msg['role'] == "assistant") or (hasattr(msg, 'role') and msg.role == "assistant")
            else SystemMessage(content=msg['content'] if isinstance(msg, dict) else msg.content)
            for msg in messages
        ]
    
    return chat_history

async def process_chat(
    current_user, 
    anonymous_session_id, 
    chat, 
    messages, 
    message, 
    title_chain, 
    db: Session,
    rag_chain
):
    """
    Process the chat message and return a response.
    
    Args:
        current_user: The current authenticated user or None
        anonymous_session_id: The anonymous session ID or None
        chat: The chat object or dictionary
        messages: List of previous messages
        message: The user's new message
        title_chain: Chain for generating chat titles
        db: Database session
        rag_chain: The retrieval chain for generating responses
        
    Returns:
        ChatResponse object with the model's response
    """
    # Prepare the chat history
    chat_history = prepare_chat_history(messages)

    # Process the user's query through the retrieval chain
    result = rag_chain.invoke({"input": message, "chat_history": chat_history})

    # Extract sources from the context
    sources = [
        {"url": doc.metadata.get('source', 'Unknown')}
        for doc in result['context']
    ]

    if current_user:
        # Save messages to database for authenticated users
        add_message(db, chat.id, MessageCreate(role="human", content=message))
        add_message(db, chat.id, MessageCreate(role="assistant", content=result.get('answer', ''), sources=sources))
        
        # Record token usage
        chat_history_tokens = sum(count_tokens(msg['content'] if isinstance(msg, dict) else msg.content) for msg in chat_history)
        tokens_used = count_tokens(message) + count_tokens(result.get('answer', '')) + chat_history_tokens
        token_usage_data = TokenUsageCreate(user_id=current_user.id, tokens_used=tokens_used)
        db_token_usage = TokenUsage(**token_usage_data.dict())
        db.add(db_token_usage)
        db.commit()
    else:
        # Save messages to Redis for anonymous users
        current_time = datetime.utcnow().isoformat()
        
        # Convert existing messages to dictionaries if they're Message objects
        messages_as_dicts = []
        for msg in messages:
            if hasattr(msg, 'dict'):
                # If it's a Pydantic model, use the dict method
                messages_as_dicts.append(msg.dict())
            elif isinstance(msg, dict):
                # If it's already a dict, use it as is
                messages_as_dicts.append(msg)
        
        # Add new messages
        new_messages = messages_as_dicts + [
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(get_chat_id(chat)),
                "role": "human",
                "content": message,
                "created_at": current_time,
                "sources": None
            },
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(get_chat_id(chat)),
                "role": "assistant",
                "content": result.get('answer', ''),
                "created_at": current_time,
                "sources": sources
            }
        ]
        await save_anonymous_chat_messages(anonymous_session_id, str(get_chat_id(chat)), new_messages)
    
    return ChatResponse(chat_id=str(get_chat_id(chat)), answer=result['answer'], sources=sources) 