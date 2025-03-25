# dJetLawyer ChatBot Backend

This is the backend for the dJetLawyer ChatBot, a sophisticated AI-powered legal assistant.

## Setup

1. Clone the repository
2. Create a virtual environment: `python3.10 -m venv ChatBotBackend`
3. Activate the virtual environment:
   - On Windows: `venv\Scripts\activate`
   - On macOS and Linux: `source ChatBotBackend/bin/activate`
4. Install dependencies: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and fill in the required environment variables
6. Set up the database:
   - Create a PostgreSQL database
   - Update the `DATABASE_URL` in `.env` with your database credentials
7. Run database migrations: `alembic upgrade head`
8. Start the server: `uvicorn main:app --reload`

## Features

### Chat Sharing

The system supports sharing chat conversations publicly:

- Authenticated users can share their chats with a public link
- Anonymous users can also share their chats, which will be saved from Redis to the permanent database
- Shared chats are accessible to anyone with the link without requiring authentication
- Shared chats maintain all original messages and source references

#### Interactive Shared Chats

- Users can continue the conversation from a shared chat
- The system creates a separate copy of the shared chat for each user who continues it
- For anonymous users, the conversation history is stored in Redis with the regular usage limits
- For authenticated users, a new chat is created in their account with the shared chat's history
- API supports passing previous messages as context when creating a new chat

To share a chat:
- API endpoint: `POST /api/v1/chat/chats/{chat_id}/share` (for authenticated users)
- API endpoint: `POST /api/v1/chatbot/share-anonymous-chat` (for anonymous users)

To view a shared chat:
- API endpoint: `GET /api/v1/chat/shared/{chat_id}`

To continue a shared chat:
- API endpoint: `POST /api/v1/chatbot/chat` with the `previous_messages` parameter

## API Documentation

Once the server is running, you can access the API documentation at `http://localhost:8000/docs`.

## Testing

To run tests, use the command: `./run_tests.sh`

## Deployment

For production deployment, consider the following:

1. Use a production WSGI server like Gunicorn
2. Set up HTTPS
3. Use environment variables for all sensitive information
4. Set up proper logging
5. Configure a production-ready database
6. Set up monitoring and error tracking
