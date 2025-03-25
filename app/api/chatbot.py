__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
import os
from fastapi import APIRouter, HTTPException, Depends, Request
from sqlalchemy.orm import Session
from app.schemas.chatbot import ChatRequest, ChatResponse, Source
from app.schemas.chat import PublicChat
from app.utils.model_init import initialize_models
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from app.core.deps import get_db, get_current_user, get_optional_current_user
from app.models.user import User
from app.services.chat import add_message, get_chat, create_chat, get_chat_messages, save_anonymous_chat_to_db
from app.schemas.chat import ChatCreate, MessageCreate
import uuid
import json
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough, RunnableSequence
from langchain_google_genai import ChatGoogleGenerativeAI
from tiktoken import encoding_for_model 
from app.schemas.usage import TokenUsageCreate
from app.models.token_usage import TokenUsage
from typing import Optional
from app.services.anonymous_chat import get_anonymous_message_count, increment_anonymous_message_count, get_anonymous_chat_messages, save_anonymous_chat_messages
from datetime import datetime


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

# Count the tokens in the message
def count_tokens(text: str) -> int:
    enc = encoding_for_model("gpt-4")
    return len(enc.encode(text))

# Summarize the chat history when it exceeds 3000 tokens
def summarize_chat_history(chat_history):
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

# At the top of the file or in an appropriate scope
def get_chat_id(chat_obj):
    if isinstance(chat_obj, dict):
        return chat_obj["id"]
    else:
        return chat_obj.id

@router.post("/chat", response_model=ChatResponse)
async def chat(
    request: Request,
    chat_request: ChatRequest, 
    db: Session = Depends(get_db), 
    current_user: Optional[User] = Depends(get_optional_current_user)
):
    try:
        # Get or create anonymous session ID from request headers
        anonymous_session_id = request.headers.get('x-anonymous-session-id')
        print(f"Anonymous session ID: {anonymous_session_id}")
        print(f"Current user: {current_user}")
        print(f"Chat ID: {chat_request.chat_id}")
        
        # Check message limit for anonymous users
        if not current_user:
            if not anonymous_session_id:
                raise HTTPException(status_code=400, detail="Anonymous session ID required")
            
            # Get message count from Redis
            message_count = await get_anonymous_message_count(anonymous_session_id)
            if message_count >= 5:
                # Return a success response with a limit_reached flag instead of an error
                return ChatResponse(
                    chat_id="limit_reached",
                    answer="Message limit reached. Please login to continue.",
                    sources=[],
                    limit_reached=True
                )
            
            # Increment message count
            await increment_anonymous_message_count(anonymous_session_id)

            # Get the previous messages from the shared chat for anonymous users
            previous_messages = getattr(chat_request, 'previous_messages', None)
        
        # Get the previous messages from the shared chat for logged in users
        previous_messages = getattr(chat_request, 'previous_messages', None)

        # If there's a chat ID, usually in subsequent anonymous messages
        if chat_request.chat_id:
            try:
                chat_request.chat_id = uuid.UUID(chat_request.chat_id)
            except ValueError:
                # If chat_id is not a valid UUID, create a new chat
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
                return await process_chat(
                    current_user, anonymous_session_id, chat, messages, 
                    chat_request.message, title_chain, db
                )
            
            # Check if we need to transfer an anonymous chat to a logged-in user
            chat_transfer_needed = False
            
            if current_user and anonymous_session_id:
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
                        chat_transfer_needed = True
                    else:
                        # No anonymous chat to transfer, create a new chat
                        chat_title = title_chain.invoke({"message": chat_request.message})
                        chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
                        print(f"No anonymous chat found, created new chat with ID: {chat.id}")
                        messages = []
                else:
                    # User's own chat exists
                    messages = get_chat_messages(db, chat.id)
            elif current_user:
                # Authenticated user, no anonymous session ID
                chat = get_chat(db, chat_request.chat_id)
                if not chat or chat.user_id != current_user.id:
                    raise HTTPException(status_code=404, detail="Chat not found")
                messages = get_chat_messages(db, chat.id)
            else:
                # Anonymous user
                messages = await get_anonymous_chat_messages(anonymous_session_id, str(chat_request.chat_id))
                if not messages:
                    # If no messages found for this chat ID, create a new chat
                    chat = {"id": uuid.uuid4()}
                    messages = []
                else:
                    chat = {"id": chat_request.chat_id}
        else:
            # If there's no chat ID, usually in the first message sent to the chatbot
            if current_user:
                # Create new chat for logged in users
                chat_title = title_chain.invoke({"message": chat_request.message})
                chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
                messages = []
            else:
                # Create new chat ID for anonymous users
                chat = {"id": uuid.uuid4()}
                messages = []
        
        return await process_chat(
            current_user, anonymous_session_id, chat, messages, 
            chat_request.message, title_chain, db
        )
        
    except Exception as e:
        print(f"Status Code: 500, Detail: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def process_chat(current_user, anonymous_session_id, chat, messages, message, title_chain, db):
    """Process the chat message and return a response."""
    # Check the total tokens in the chat history
    total_tokens = sum(count_tokens(msg['content'] if isinstance(msg, dict) else msg.content) for msg in messages)

    # If total tokens exceed 1500, summarize the chat history
    if total_tokens > 1500:
        summary = summarize_chat_history(messages)
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