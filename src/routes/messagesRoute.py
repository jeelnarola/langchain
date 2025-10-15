from fastapi import APIRouter
from controllers.messagesController import get_messages
messageRouter = APIRouter()

@messageRouter.get("/{session_id}")
async def fetch_messages(session_id: str, limit: int = 20):
    messages = await get_messages(session_id, limit)
    # Reverse so oldest first
    messages.reverse()
    return {"messages": messages}
