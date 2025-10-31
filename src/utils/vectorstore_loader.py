import os
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

load_dotenv()

def load_global_vectorstore():
    """Load global vectorstore on startup if it exists"""
    VECTOR_DIR = "./chroma_vectors"
    global_path = os.path.join(VECTOR_DIR, "global")
    
    if os.path.exists(global_path):
        OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
        embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)
        return Chroma(persist_directory=global_path, embedding_function=embeddings)
    return None
