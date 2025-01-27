__import__('pysqlite3')
import sys
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
from fastapi import APIRouter, HTTPException, Depends
from sqlalchemy.orm import Session
from app.schemas.chatbot import ChatRequest, ChatResponse, Source
from app.utils.model_init import initialize_models
from langchain_core.messages import HumanMessage, SystemMessage
from app.core.deps import get_db, get_current_user
from app.models.user import User
from app.services.chat import add_message, get_chat, create_chat, get_chat_messages
from app.schemas.chat import ChatCreate, MessageCreate
import uuid
import json
from langchain_core.prompts import PromptTemplate
from langchain_openai import ChatOpenAI
from langchain_core.runnables import RunnablePassthrough, RunnableSequence
from tiktoken import encoding_for_model 
from app.schemas.usage import TokenUsageCreate
from app.models.token_usage import TokenUsage


router = APIRouter()

# Initialize the RAG chain
rag_chain = initialize_models()
llm = ChatOpenAI(temperature=0.7)

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
    return summary_chain.invoke({"chat_history": "\n".join([f"{msg.role}: {msg.content}" for msg in chat_history])})


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    try:
        # Check if chat_id is provided
        if request.chat_id:
            request.chat_id = uuid.UUID(request.chat_id)
            # Get the existing chat
            chat = get_chat(db, request.chat_id)
            if not chat or chat.user_id != current_user.id:
                raise HTTPException(status_code=404, detail="Chat not found")
            
            # Retrieve chat history from the database
            messages = get_chat_messages(db, chat.id)
        else:
            # Create a new chat
            chat_title = title_chain.invoke({"message": request.message})
            chat = create_chat(db, current_user.id, ChatCreate(title=chat_title))
            messages = []  # Empty history for new chats

        # Check the total tokens in the chat history
        total_tokens = sum(count_tokens(msg.content) for msg in messages)

        # If total tokens exceed 3000, summarize the chat history
        if total_tokens > 1500:
            summary = summarize_chat_history(messages)
            chat_history = [SystemMessage(content=f"Chat history summary: {summary}")]
        else:
            # Convert chat history to the format expected by the chain
            chat_history = [
                (HumanMessage if msg.role == "human" else SystemMessage)(content=msg.content)
                for msg in messages
            ]

        # Process the user's query through the retrieval chain
        result = rag_chain.invoke({"input": request.message, "chat_history": chat_history})

        # Extract sources from the context
        sources = [
            {"url": doc.metadata.get('source', 'Unknown')}
            for doc in result['context']
        ]

        # Save the user's message and the bot's response to the database
        add_message(db, chat.id, MessageCreate(role="human", content=request.message))
        add_message(db, chat.id, MessageCreate(role="assistant", content=result.get('answer', ''), sources=sources))


        # Record token usage
        chat_history_tokens = sum(count_tokens(msg.content) for msg in chat_history)
        tokens_used = count_tokens(request.message) + count_tokens(result.get('answer', '')) + chat_history_tokens
        token_usage_data = TokenUsageCreate(user_id=current_user.id, tokens_used=tokens_used)
        db_token_usage = TokenUsage(**token_usage_data.dict())
        db.add(db_token_usage)
        db.commit()
        
        return ChatResponse(chat_id=str(chat.id), answer=result['answer'], sources=sources)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))