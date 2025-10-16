
from dotenv import load_dotenv
import os
from mem0 import MemoryClient

load_dotenv()
client = MemoryClient(os.getenv('MEM0_KEY'))

# Add messages to mem0
def add_to_mem0(user_id: str, messages: list):
    try:
        client.add(messages, user_id=user_id)
        print('\033[92m=====user_id=====\033[0m', user_id)
    except Exception as e:
        print(f"❌ Failed to add messages to mem0: {e}")

# Retrieve messages from mem0
def retrieve_mem0(user_id: str, question: str) -> str:
    """
    Retrieve relevant mem0 memories for a user based on a question.
    """
    try:
        print('\033[92m=====mem0 query=====\033[0m', question)
        results = client.search(user_id=user_id, query=question)
        print('\033[92m=====mem0 search results=====\033[0m', results)

        if not results:
            return "No relevant memory found."

        # Access the correct key: 'memory'
        return "\n".join(f"- {entry['memory']}" for entry in results)
    except Exception as e:
        print(f"❌ Failed to retrieve mem0 memory: {e}")
        return "Error retrieving memory."