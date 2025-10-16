import uuid
import os
from dotenv import load_dotenv
from datetime import datetime
from typing import Dict, Any, Optional
import tiktoken
from langchain_community.chat_models import ChatOpenAI
import json

# We no longer keep a separate sessions dict here — we’ll use the global from controllers.
import re

from services.sessionService import insert_session,update_session_name
from config.database import get_db
from services.messageService import insert_message
from openai import OpenAI
load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=OPENAI_API_KEY)


def create_session(name: Optional[str] = None) -> Dict[str, Any]:
    sid = str(uuid.uuid4())
    session_name = name or "New Chat"
    created_at = datetime.utcnow().isoformat()

    # Get database session and insert into DB
    db = next(get_db())
    insert_session(db, session_name)

    return {
        "id": sid,
        "name": session_name,
        "created_at": created_at,
    }

# Updated: remove the first 'sessions' argument
def updated_sessions(session_id: str, role: str, content: str):
    from controllers import askControllers

    sessions = askControllers.sessions

    if session_id not in sessions:
        raise KeyError("Session not found")


    if (
        role == "user"
        and sessions[session_id]["name"] in (None, "", "New Chat")
        and not any(msg["role"] == "user" for msg in sessions[session_id]["messages"])
    ):
        preview = content.strip()
        if len(preview) > 50:  # consistent with DB
            preview = preview[:50] + "..."
        sessions[session_id]["name"] = preview

        # Update DB as well - convert session_id to int if needed
        try:
            db = next(get_db())
            session_id_int = int(session_id) if session_id.isdigit() else None
            if session_id_int:
                update_session_name(db, session_id_int, preview)
        except (ValueError, AttributeError):
            # Skip DB update if session_id is not a valid integer
            pass

    sessions[session_id]["messages"].append({"role": role, "content": content})

def count_tokens(text: str, model_name="gpt-3") -> int:
    try:
        encoding = tiktoken.encoding_for_model(model_name)
    except KeyError:
        encoding = tiktoken.get_encoding("cl100k_base")
    return len(encoding.encode(text))

def store_message_db(session_id: str, role: str, message: str):
    import json
    if isinstance(message, dict):
        message = json.dumps(message)
    try:
        db = next(get_db())
        session_id_int = int(session_id) if session_id.isdigit() else None
        if session_id_int:
            insert_message(db, session_id_int, role, message)
    except (ValueError, AttributeError):
        # Skip DB insert if session_id is not a valid integer
        pass


