import asyncio
from services.messageService import fetch_message_by_session
from config.database import get_db

async def get_messages(session_id: str, limit: int = 20):
    db = next(get_db())
    try:
        rows = fetch_message_by_session(db, int(session_id), limit)
        return rows
    finally:
        db.close()
