import os
import json
import datetime
from typing import Dict, Any

from dotenv import load_dotenv
from langchain_openai import OpenAIEmbeddings
from openai import OpenAI
from sqlalchemy.orm import Session

# 🧩 Internal imports
from validations.schemas import MessageIn
from utils.createSession import updated_sessions, store_message_db
from utils.toolAgent import ToolAgent
from utils.toolSchema import tools_schema
from tools.toolmanager import handle_tool_call, parse_use_mcp_tool

# =========================================================
# 🔧 Environment & Globals
# =========================================================
load_dotenv()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)
embeddings = OpenAIEmbeddings(openai_api_key=OPENAI_API_KEY)

# Sessions in-memory
sessions: Dict[str, Dict[str, Any]] = {}

# =========================================================
# 💬 Core Function — Ask in Session
# =========================================================
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