import asyncio
from services.messageService import fetch_message_by_session
from config.database import SessionLocal

async def get_messages(session_id: str, limit: int = 20):
    loop = asyncio.get_event_loop()
    db = SessionLocal()
    try:
        rows = await loop.run_in_executor(None, fetch_message_by_session, db, int(session_id), limit)
        return rows
    finally:
        db.close()
