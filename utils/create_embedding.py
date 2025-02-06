import openai
import numpy as np

# Modified: Added import for environment variables
from dotenv import load_dotenv
import os

# Modified: Load environment variables from .env file
load_dotenv()

# Modified: Set up the OpenAI API key from environment variable
openai.api_key = os.getenv("OPENAI_API_KEY")

def get_embedding(text: str, model: str = "text-embedding-3-small") -> list[float]:
    """
    Get the embedding for a given text using the specified OpenAI model.
    
    Args:
        text (str): The input text to embed.
        model (str): The name of the OpenAI embedding model to use.
    
    Returns:
        list[float]: The embedding vector as a list of floats.
    
    Raises:
        Exception: If there's an error in the API call.
    """
    # Modified: Updated to use the latest OpenAI client
    client = openai.OpenAI()
    
    try:
        # Modified: Updated API call to match the latest OpenAI Python client syntax
        response = client.embeddings.create(input=[text], model=model)
        embedding = response.data[0].embedding
        return embedding
    except Exception as e:
        print(f"Error getting embedding: {str(e)}")
        return []

# Example usage
text = "Agricultural Credit Guarantee Scheme Fund Act"
embedding = get_embedding(text)

if embedding:
    print(f"Input text: {text}")
    print(f"Embedding dimension: {len(embedding)}")
    print(f"embedding: {embedding}")
    
    # Modified: Added numpy array conversion for additional operations
    # embedding_array = np.array(embedding)
    # print(f"Embedding mean: {embedding_array.mean()}")
    # print(f"Embedding standard deviation: {embedding_array.std()}")