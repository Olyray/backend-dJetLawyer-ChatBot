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

async def generate_attachment_summary(llm, attachment_type, file_name, content):
    """
    Generate a summary for an attachment using the provided LLM.
    
    Args:
        llm: The language model to use for generating summaries
        attachment_type: Type of attachment (document, image, audio)
        file_name: Name of the attachment file
        content: Content of the attachment
        
    Returns:
        str: Generated summary or description of the attachment
    """
    try:
        if attachment_type == "document":
            # For documents, summarize the text content
            prompt = f"Please summarize the following document content from '{file_name}'. Focus on key information, main points, and any actionable items:\n\n{content}"
            
            # Use the LLM to generate a summary with the correct message format
            try:
                from langchain_core.messages import HumanMessage
                
                response = await llm.ainvoke([
                    HumanMessage(content=prompt)
                ])
                
                summary = response.content.strip()
                return summary
            except Exception as e:
                print(f"Error generating document summary for {file_name}: {str(e)}")
                return f"Document '{file_name}' (unable to generate summary)"
            
        elif attachment_type == "image":
            # For images, generate a description using the multimodal capabilities
            prompt = f"Please transcribe this image '{file_name}'"
            
            # Create a multimodal message for the LLM using the correct format (role/content)
            try:
                # Use LangChain's message format for Gemini
                from langchain_core.messages import HumanMessage
                
                # Create a message with text and image
                response = await llm.ainvoke([
                    HumanMessage(
                        content=[
                            {"type": "text", "text": prompt},
                            content  # This is the image data already formatted correctly
                        ]
                    )
                ])
                
                description = response.content.strip()
                return description
            except Exception as e:
                print(f"Error generating image description for {file_name}: {str(e)}")
                return f"Image '{file_name}' (unable to generate description)"
            
        elif attachment_type == "audio":
            # For audio, request a description
            # Note: This assumes the LLM can process audio. If not, we'll need a specialized service
            prompt = f"Please transcribe the content of this audio file '{file_name}'. Return just the transcription, no other text."
            
            # Some LLMs might not directly support audio processing
            # This is a placeholder and may need to be adjusted based on the LLM's capabilities
            try:
                from langchain_core.messages import HumanMessage
                
                response = await llm.ainvoke([
                    HumanMessage(
                        content=[
                            {"type": "text", "text": prompt},
                            {"type": "media", "data": content["data"], "mime_type": content["mime_type"]}
                        ]
                    )
                ])
                
                transcription = response.content.strip()
                return transcription
            except Exception as e:
                # Fallback for LLMs that don't support audio
                print(f"Audio processing error: {str(e)}")
                return f"Audio file '{file_name}' (audio processing not available)"
                    
    except Exception as e:
        # If summarization fails for any reason, add a basic description
        print(f"Error generating summary for {file_name}: {str(e)}")
        return f"Attachment '{file_name}' (type: {attachment_type})"

async def process_attachments(db: Session, attachments: List[AttachmentData], llm=None) -> tuple:
    """
    Process attachments, generate summaries, and prepare for inclusion in the message.
    
    Args:
        db: Database session
        attachments: List of attachment data
        llm: Language model for generating summaries (optional)
        
    Returns:
        Tuple of (attachment_content, attachment_summaries, attachments_for_message)
    """
    # For storing attachments that will be saved to the database
    attachments_for_message = []
    
    # For document text content
    text_content = []
    
    # For image attachments
    image_content = []
    
    # For audio attachments
    audio_content = []
    
    # For mapping attachment to their processed content (for summary generation)
    attachment_content_map = []
    
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
            base64_image = encode_file_to_base64(file_path)
            image_data = {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{attachment.file_type};base64,{base64_image}"
                }
            }
            image_content.append(image_data)
            
            # Store for summary generation
            attachment_content_map.append(("image", attachment.file_name, image_data))
            
        elif attachment.file_type.startswith('audio/'):
            # For audio, use media type which is supported by Gemini API
            base64_audio = encode_file_to_base64(file_path)
            audio_data = {
                "type": "media",
                "mime_type": attachment.file_type,
                "data": base64_audio
            }
            audio_content.append(audio_data)
            
            # Store for summary generation
            attachment_content_map.append(("audio", attachment.file_name, audio_data))
            
        else:
            # For documents, extract text content
            document_text = await extract_text_from_document(file_path)
            if document_text:
                # Add as text content with document reference
                formatted_text = f"\nContent from document '{attachment.file_name}':\n{document_text}"
                text_content.append(formatted_text)
                
                # Store for summary generation
                attachment_content_map.append(("document", attachment.file_name, document_text))
    
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
        
    # Add audio with the same pattern
    if audio_content:
        attachment_content.append(
            ("human", audio_content)
        )
    
    # Generate summaries for attachments if LLM is provided
    attachment_summaries = []
    
    if llm and attachment_content_map:
        for attachment_type, file_name, content in attachment_content_map:
            summary = await generate_attachment_summary(llm, attachment_type, file_name, content)
            attachment_summaries.append(summary)
    
    return attachment_content, attachment_summaries, attachments_for_message

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
    attachment_summaries = []
    attachments_for_message = []
    
    if attachments:
        # Get LLM for generating summaries
        from langchain_google_genai import ChatGoogleGenerativeAI
        import os
        
        llm_for_summaries = ChatGoogleGenerativeAI(
            google_api_key=os.getenv('GEMINI_API_KEY'),
            model='gemini-2.0-flash',
            temperature=0.5
        )
        
        # Process attachments and generate summaries
        attachment_content, attachment_summaries, attachments_for_message = await process_attachments(
            db, attachments, llm_for_summaries
        )
    
    # Combine user message with attachment summaries
    if attachment_summaries:
        message += "\n\nAttachment summaries:\n" + "\n".join(attachment_summaries)
    
    # Process the combined query through the retrieval chain
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