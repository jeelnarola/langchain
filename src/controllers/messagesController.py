import asyncio
from services.messageService import fetch_message_by_session
async def get_messages(session_id: str, limit: int = 20):
    loop = asyncio.get_event_loop()
    rows = await loop.run_in_executor(None, fetch_message_by_session, session_id, limit)
    return rows
