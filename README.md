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


## Files

1. createPineCone.py: This is the script for uploading files to pinecone. Usage is `python createPineCone.py load_data` to add data to the pinecone vector store. `python createPineCone.py` to test what has been uploaded to the vector store.

2. createVectorDatabase.py: This is the script for creating the local Chroma Vector database. It has been deprecated because I am no longer using a local Chroma vector database.