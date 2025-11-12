from validations.schemas import MessageIn
import os
from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from utils.toolSchema import tools_schema
import datetime
from typing import Dict, Any
from openai import OpenAI
from utils.toolAgent import ToolAgent
from sqlalchemy.orm import Session
from utils.createSession import (
    updated_sessions,
    store_message_db,
)

load_dotenv()
sessions: Dict[str, Dict[str, Any]] = {}
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# client = OpenAI(api_key=OPENAI_API_KEY)
from google import genai
client = genai.Client(api_key=GEMINI_API_KEY)

# VECTOR_DIR = "./chroma_vectors"  # chroma vectorstore directory
# os.makedirs(VECTOR_DIR, exist_ok=True)

# # async def ask_in_session(session_id: str, data: MessageIn):
#     rows = get_all_vector_paths()
#     # print("----------------")
#     if not rows:
#         return JSONResponse(
#             status_code=400, content={"error": "No documents uploaded yet"}
#         )

#     #### Only See
#     ### Vectore store loading
#     #     # Merge all indexes into one
#     #     # combined_store = None
#     #     # for row in rows:
#     #     #     store = FAISS.load_local(row["vector_path"], embeddings, allow_dangerous_deserialization=True)
#     #     #     if combined_store is None:
#     #     #         combined_store = store
#     #     #     else:
#     #     #         combined_store.merge_from(store)

#     #     # # Search in the combined store
#     #     # retriever_docs = combined_store.similarity_search(data.q, k=5)
#     #     # context = "\n\n".join([doc.page_content for doc in retriever_docs])

#     ### Chroma store loading
#     # Load PDF stores (Chroma)
#     retriever_docs = []
#     for row in rows:
#         store = Chroma(
#             persist_directory=row["vector_path"], embedding_function=embeddings
#         )
#         retriever_docs.extend(store.similarity_search(data.q, k=2))

#     retriever_docs = retriever_docs[:5]
#     context = "\n\n".join([doc.page_content for doc in retriever_docs])

#     # Conversation history
#     history_text = ""
#     if session_id not in sessions:
#         sessions[session_id] = {
#             "id": session_id,
#             "name": "Auto-created session",
#             "created_at": datetime.utcnow().isoformat(),
#             "messages": [],
#         }

#         print(f"Received ask request for session {session_id} with question: {data.q}")

#         last_messages = sessions[session_id]["messages"][-8:]
#         history_text = "\n".join(
#             [f"{m['role']}: {m['content']}" for m in last_messages]
#         )

#         # Save user message
#         add_message(session_id, "user", data.q)
#         store_message_db(session_id, "user", data.q)

#     # --- Retrieve memory for this query ---
#     memory_text = retrieve_memory_db(k=3)

#     # Prompt
#     prompt = PromptTemplate(
#         input_variables=["history", "context", "memory", "question"],
#         template="""
#         You are an assistant that answers questions using ONLY the provided context,
#         conversation history, and user profile memory.

#         User Profile Memory:
#         {memory}

#         Conversation History:
#         {history}

#         Context from Documents:
#         {context}

#         Question: {question}

#         If the answer isn't present in context or memory, reply "I don't know."
#         Answer:
#         """,
#     )

#     handler = FastAPIStreamingCallbackHandler()
#     llm = ChatOpenAI(
#         model="gpt-3.5-turbo-1106",
#         temperature=0,
#         streaming=True,
#         callbacks=[handler],
#     ).bind_tools([weather_tool])

#     chain = prompt | llm

#     async def run_and_capture():
#         result = await chain.ainvoke(
#             {
#                 "history": history_text,
#                 "context": context,
#                 "memory": memory_text,
#                 "question": data.q,
#             }
#         )

#         print("RAW LLM RESULT:", result)

#         final_text = None

#         # 🔎 Check if the LLM decided to call a tool
#         if hasattr(result, "tool_calls") and result.tool_calls:
#             for call in result.tool_calls:
#                 print(f"Tool called: {call['name']} with args {call['args']}")
#                 if call["name"] == "weather_tool":
#                     # Execute the tool manually
#                     weather_result = weather_tool.invoke(call["args"])
#                     print("Weather tool result:", weather_result)
#                     final_text = str(weather_result)
#         else:
#             # If no tool was called, just use the model’s normal response
#             final_text = result.content

#         # Save assistant response
#         add_message(session_id, "assistant", final_text)
#         store_message_db(session_id, "assistant", final_text)

#         # --- Extract new memory snippet ---
#         recent_turns = sessions[session_id]["messages"][-4:]  # last few turns
#         facts = extract_memory(recent_turns)  # should return dict

#         if facts:
#             for field, value in facts.items():
#                 save_memory_db(field, value)


#     asyncio.create_task(run_and_capture())

#     async def token_streamer():
#         async for token in handler.stream_tokens():
#             yield token
#         yield "\n"

#     return StreamingResponse(token_streamer(), media_type="text/plain")


# ---------------- Ask in session ----------------

async def ask_in_session(session_id: str, data: "MessageIn",db: Session) -> str:
    try:
        if session_id not in sessions:
            sessions[session_id] = {
                "id": session_id,
                "name": "Auto-created session",
                "created_at": datetime.datetime.utcnow().isoformat(),
                "messages": [],
            }

        updated_sessions(session_id, "user", data.question)
        store_message_db(session_id, "user", data.question)
        
        # tools_schema = await tools_schema()
        agent = ToolAgent(session_id, client, tools_schema, db)
        task = data.question
        conversation_history = sessions.get(session_id, {}).get("messages", [])
        mode = "action"
        # ✅ Await a normal coroutine (string), not a generator
        result = await agent.start_task(task, conversation_history, mode)
        return result
    except Exception as e:
        print("Error in ask_in_session:", e)
        return "Error processing the request."
