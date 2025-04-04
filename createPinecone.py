from dotenv import load_dotenv
import os
import time
import sys
import json
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.chains.retrieval import create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain
from langchain import hub
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_pinecone import PineconeEmbeddings, PineconeVectorStore
from langchain.schema import Document
from langchain_community.document_loaders import PyPDFLoader
from langchain_google_genai import ChatGoogleGenerativeAI
from pinecone import Pinecone, ServerlessSpec
from tqdm import tqdm
import random


load_dotenv()

# Load the documents
def load_documents ():
    # Load the JSON file containing PDF mappings
    current_dir = os.path.dirname(os.path.abspath(__file__))
    json_path = os.path.join(current_dir, "downloadBlogPosts", "downloaded_pdfs.json")
    with open(json_path, 'r') as f:
        source_mapping = json.load(f)
    
    # Load the PDFs from the specified directory
    document_path = "./downloadBlogPosts/blog_pdfs/dJetLawyer_LFN/C"
    documents = []
    for filename in os.listdir(document_path):
        if filename.endswith('.pdf'):
            file_path = os.path.join(document_path, filename)
            loader = PyPDFLoader(file_path)
            pdf_docs = loader.load()

            # Add URL metadata to each page of the PDF
            url = source_mapping.get(f"blog_pdfs/dJetLawyer_LFN/C/{filename}", "Unknown URL")
            for doc in pdf_docs:
                doc.metadata["source"] = url
            documents.extend(pdf_docs)
    print(f"Loaded {len(documents)} documents")

    return documents

# Connect the APIs
# Split and chunk the sourcce documents. 
def chunk_source_documents(source):
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200
    )
    chunked_document = text_splitter.split_documents(source)
    return chunked_document

# Add it to the pinecone vector store
def add_to_vector_store(chunked_document):
    embeddings = OpenAIEmbeddings(
        model = 'text-embedding-3-small',
        openai_api_key = os.getenv('OPENAI_API_KEY')
    )
    pc = Pinecone(api_key=os.getenv('PINECONE_API_KEY'))
    index_name = 'djetlawyer-chatbot'
    if index_name not in pc.list_indexes().names():
        pc.create_index(
            name=index_name,
            dimension=1536,
            metric='cosine',
            spec=ServerlessSpec(cloud = 'aws', region='us-east-1')
        )
        while not pc.describe_index(index_name).status['ready']:
            time.sleep(1)
    if len(sys.argv) > 1 and sys.argv[1] == 'load_data':
        print('Loading data into Pinecone')
        docsearch = PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embeddings,
            namespace='djetlawyer-blog-posts'
        )

        # load the json of saved sources
        try:
            with open('added_document.json', 'r') as file:
                added_documents = json.load(file)
        except FileNotFoundError:
            added_documents = []
        # Filter out documents that haven't been uploaded
        not_uploaded = [ doc for doc in chunked_document if doc.metadata["source"] not in added_documents ]
        # Now use tdqm to add the documents that haven't been filtered. 
        batch_size = 100

        for i in tqdm(range(0, len(not_uploaded), batch_size)):
            documents_to_add = not_uploaded[i: i + batch_size]
            sources_to_be_added = [ doc.metadata["source"] for doc in documents_to_add ]
            try:
                docsearch.add_documents(documents_to_add)
            except Exception as e:
                print(f"Error adding documents: {e}")
                print("waiting before retrying...")
                time.sleep(60)
            try:
                with open('added_documents.json', 'r') as file:
                    existing_sources = json.load(file)
            except FileNotFoundError:
                    existing_sources = []
            new_and_existing_sources = list(set(existing_sources + sources_to_be_added))
            new_and_existing_sources.sort()
            with open('added_documents.json', 'w') as file:
                json.dump(new_and_existing_sources, file, indent=4)
            # time.sleep(random.uniform(5, 10))
    
        print('Loaded data into Pinecone')
    else:
        print('Using existing index')
        print()
        docsearch = PineconeVectorStore.from_existing_index(
            index_name=index_name,
            embedding=embeddings,
            namespace='djetlawyer-blog-posts'
        )

    time.sleep(5)
    return docsearch


def create_chatbot(vector_store):
    retriever = vector_store.as_retriever(search_kwargs={'k': 3})

    # llm = ChatOpenAI(
    #     openai_api_key=os.getenv('OPENAI_API_KEY'),
    #     model_name='gpt-4o-mini',
    #     temperature=0.5
    # )

    llm = ChatGoogleGenerativeAI(
        google_api_key=os.getenv('GEMINI_API_KEY'),
        model='gemini-2.0-flash',
        temperature=0.5
    )

    qa_system_prompt = (
        """   
        You are a knowledgeable Nigerian lawyer. Law students and lawyers would ask you questions, and you're to answer from the documents provided. 
        All your responses must be backed up with Nigerian legal authorities. This means that you must either provide Nigerian statutes or case law to support your position. 
        If you need to find statutes or case law to support your position, check the context I have attached.

        """
        "\n\n"
        "{context}"
    )

    prompt = ChatPromptTemplate.from_messages(
        [
            ("system", qa_system_prompt),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
        ]
    )

    context_chain = create_stuff_documents_chain(llm, prompt)

    rag_chain = create_retrieval_chain(retriever, context_chain)

    print("Start chatting with the AI! Type 'exit' to end the conversation.")

    chat_history = []
    while True:
        query = input("You: ")
        if query.lower() == "exit":
            break

        result = rag_chain.invoke({"input": query, "chat_history": chat_history})

        print("\nRetrieved Context:")
        for doc in result['context']:
            print(f"Source: {doc.metadata.get('source', 'Unknown')}")
            print(f"Content: {doc.page_content[:200]}...")  # Print first 200 characters
            print("-" * 50)

        print(f"AI: {result['answer']}")
        # Update the chat history
        chat_history.append(HumanMessage(content=query))
        chat_history.append(SystemMessage(content=result["answer"]))


def main():
    if len(sys.argv) > 1 and sys.argv[1] == 'load_data':
        sources = load_documents()
        chunked_documents = chunk_source_documents(sources)
        vector_store = add_to_vector_store(chunked_documents)
    else:
        chunked_documents = []
        vector_store = add_to_vector_store(chunked_documents)
    create_chatbot(vector_store)

    

if __name__ == "__main__":
    main()
