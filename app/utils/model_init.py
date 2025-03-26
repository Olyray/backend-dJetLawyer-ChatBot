import os
from dotenv import load_dotenv
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain_community.vectorstores import Chroma
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_pinecone import PineconeEmbeddings, PineconeVectorStore
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables
load_dotenv()

def initialize_models():
    # Define the persistent directory
    current_dir = os.path.dirname(os.path.abspath(__file__))
    persistent_directory = os.path.join(current_dir, "..", "..", "db", "chroma_db_with_metadata")
    embeddings = OpenAIEmbeddings(
        model = 'text-embedding-3-small',
        openai_api_key = os.getenv('OPENAI_API_KEY')
    )

    # Initialize embeddings and vector store
    db = PineconeVectorStore.from_existing_index(
            index_name='djetlawyer-chatbot',
            embedding=embeddings,
            namespace='djetlawyer-blog-posts'
        )

    # Initialize retriever
    retriever = db.as_retriever(
        search_kwargs={"k": 3}
    )


    llm = ChatGoogleGenerativeAI(
        google_api_key=os.getenv('GEMINI_API_KEY'),
        model='gemini-2.0-flash',
        temperature=0.5
    )

    """
    # Initialize ChatOpenAI model
    llm = ChatOpenAI(model="gpt-4o")

    # Contextualize question prompt
    contextualize_q_system_prompt = (
        "Given a chat history (which might be summarized) and the latest user question "
        "which might reference context in the chat history, "
        "formulate a standalone question which can be understood "
        "without the chat history. If the chat history is summarized, "
        "use the summary to provide context. Do NOT answer the question, just "
        "reformulate it if needed and otherwise return it as is."
    )

    contextualize_q_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", contextualize_q_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    # Create a history-aware retriever
    history_aware_retriever = create_history_aware_retriever(
        llm, retriever, contextualize_q_prompt
    )
    """

    # Answer question prompt
    qa_system_prompt = (
        """   
         You are a knowledgeable Nigerian lawyer. Law students and lawyers would ask you questions. 
        All your responses must be backed up with Nigerian legal authorities. This means that you must either provide Nigerian statutes or case law to support your position. 
        If you need to find statutes or case law to support your position, check the context I have attached.
        Use the chat history to maintain context of the conversation and understand any references to previous messages.
        If the user's question refers to something mentioned earlier, use the chat history to understand the context.
        """
        "\n\n"
        "{context}"
    )

    qa_prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    # Create question answering chain
    question_answer_chain = create_stuff_documents_chain(llm, qa_prompt)

    # Create retrieval chain
    rag_chain = create_retrieval_chain(retriever, question_answer_chain)

    return rag_chain