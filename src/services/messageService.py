from sqlalchemy.orm import Session
from model.tableModel import ChatMessage, Sessions as SessionModel
from typing import List, Dict

def fetch_message_by_session(db: Session, session_id: int, limit: int = 20) -> List[Dict]:
    """
    Fetch all messages for a given session ID (most recent first).
    """
    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"role": msg.role, "message": msg.message, "created_at": msg.created_at}
        for msg in messages
    ]


def insert_message(db: Session, session_id: int, role: str, message: str):
    """
    Insert a message into chat_messages table and optionally update session name.
    """
    new_msg = ChatMessage(session_id=session_id, role=role, message=message)
    db.add(new_msg)

    # Update session name for first user message if needed
    if role == "user":
        session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if session_obj and session_obj.name in (None, "", "New Chat"):
            preview = message.strip()
            if len(preview) > 50:
                preview = preview[:50] + "..."
            session_obj.name = preview
            db.add(session_obj)

    db.commit()
