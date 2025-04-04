"""
Service module for processing chat messages through the language model.
This module contains functions for managing chat history, token counting, and generating responses.
"""

import uuid
import os
from datetime import datetime
from typing import Dict, List, Any
from sqlalchemy.orm import Session

from app.schemas.chatbot import ChatResponse, AttachmentData
from app.schemas.chat import MessageCreate
from app.schemas.usage import TokenUsageCreate
from app.models.token_usage import TokenUsage
from app.models.attachment import Attachment
from app.services.chat import add_message
from app.services.anonymous_chat import save_anonymous_chat_messages
from app.services.file_storage import encode_file_to_base64, extract_text_from_document, UPLOAD_DIR
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

async def process_attachments(db: Session, attachments: List[AttachmentData]) -> tuple:
    """
    Process attachments and prepare them for inclusion in the LLM message.
    
    Args:
        db: Database session
        attachments: List of attachment data
        
    Returns:
        Tuple of (attachment_content, attachments_for_message)
    """
    # For storing attachments that will be saved to the database
    attachments_for_message = []
    
    # For document text content
    text_content = []
    
    # For image attachments
    image_content = []
    
    for attachment_data in attachments:
        # Get attachment details from database
        attachment_id = uuid.UUID(attachment_data.id)
        attachment = db.query(Attachment).filter(Attachment.id == attachment_id).first()
        
        if not attachment:
            print(f"Attachment not found: {attachment_data.id}")
            continue
            
        # Add to attachments that will be associated with the message
        attachments_for_message.append(attachment)
            
        file_path = os.path.join(UPLOAD_DIR, attachment.file_path)
        
        # Process based on file type
        if attachment.file_type.startswith('image/'):
            # For images, add to image content list in the format expected by the LLM
            image_content.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:{attachment.file_type};base64,{encode_file_to_base64(file_path)}"
                }
            })
        else:
            # For documents, extract text content
            document_text = await extract_text_from_document(file_path)
            if document_text:
                # Add as text content with document reference
                text_content.append(f"\nContent from document '{attachment.file_name}':\n{document_text}")
    
    # Format all attachments for the model
    attachment_content = []
    
    # Add all document text with a role if needed
    if text_content:
        attachment_content.append(
            ("human", [{"type": "text", "text": "\n".join(text_content)}])
        )
    
    # Add images with the same pattern
    if image_content:
        attachment_content.append(
            ("human", image_content)
        )
    
    return attachment_content, attachments_for_message

async def process_chat(
    current_user, 
    anonymous_session_id, 
    chat, 
    messages, 
    message, 
    title_chain, 
    db: Session,
    rag_chain,
    attachments: List[AttachmentData] = None
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
        attachments: Optional list of attachments
        
    Returns:
        ChatResponse object with the model's response
    """
    # Prepare the chat history
    chat_history = prepare_chat_history(messages)

    # Process attachments if provided
    attachment_content = []
    attachments_for_message = []
    
    if attachments:
        attachment_content, attachments_for_message = await process_attachments(db, attachments)
    
    # Process the user's query through the retrieval chain
    result = rag_chain.invoke({
        "input": message,
        "chat_history": chat_history,
        "attachments": attachment_content
    })

    # Extract sources from the context
    sources = [
        {"url": doc.metadata.get('source', 'Unknown')}
        for doc in result['context']
    ]

    if current_user:
        # Save messages to database for authenticated users
        human_message = add_message(db, chat.id, MessageCreate(role="human", content=message))
        ai_message = add_message(db, chat.id, MessageCreate(role="assistant", content=result.get('answer', ''), sources=sources))
        
        # Update attachment records with message_id
        for attachment in attachments_for_message:
            attachment.message_id = human_message.id
        db.commit()
        
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
        
        # Create attachments data for storage
        attachments_data = []
        for attachment in attachments_for_message:
            attachments_data.append({
                "id": str(attachment.id),
                "file_name": attachment.file_name,
                "file_type": attachment.file_type,
                "file_size": attachment.file_size
            })
        
        # Add new messages
        new_messages = messages_as_dicts + [
            {
                "id": str(uuid.uuid4()),
                "chat_id": str(get_chat_id(chat)),
                "role": "human",
                "content": message,
                "created_at": current_time,
                "sources": None,
                "attachments": attachments_data if attachments_data else None
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