import redis.asyncio as redis
from app.core.config import settings
import json
from typing import List, Optional
from app.schemas.chat import Message
import uuid

# Initialize Redis client
redis_client = redis.from_url(f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}", encoding="utf-8", decode_responses=True)

async def get_anonymous_message_count(session_id: str) -> int:
    """Get the number of messages sent by an anonymous user."""
    count = await redis_client.get(f"anonymous:count:{session_id}")
    return int(count) if count else 0

async def increment_anonymous_message_count(session_id: str) -> int:
    """Increment the message count for an anonymous user."""
    key = f"anonymous:count:{session_id}"
    count = await redis_client.incr(key)
    # Set expiration to 24 hours
    await redis_client.expire(key, 86400)
    return count

async def get_anonymous_chat_messages(session_id: str, chat_id: str) -> List[dict]:
    """Get chat messages for an anonymous user."""
    key = f"anonymous:chat:{session_id}:{chat_id}"
    messages_json = await redis_client.get(key)
    if not messages_json:
        return []
    # Return the raw dictionaries instead of converting to Message objects
    return json.loads(messages_json)

async def save_anonymous_chat_messages(session_id: str, chat_id: str, messages: List[dict]):
    """Save chat messages for an anonymous user."""
    key = f"anonymous:chat:{session_id}:{chat_id}"
    # Messages are already in dict format, no need for conversion
    await redis_client.set(key, json.dumps(messages))
    # Set expiration to 24 hours
    await redis_client.expire(key, 86400)

async def clear_anonymous_session(session_id: str):
    """Clear all data for an anonymous session."""
    keys = await redis_client.keys(f"anonymous:*:{session_id}*")
    if keys:
        await redis_client.delete(*keys) 