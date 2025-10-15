from validations.schemas import CreateSession
from services.sessionService import fetch_sessions
from utils.createSession import create_session
from config.database import get_db
import asyncio

async def api_create_session(data: CreateSession):
    new_session = create_session(data.name)
    return new_session

async def get_session():
    loop = asyncio.get_event_loop()
    
    # Get database session
    db = next(get_db())
    
    # Run blocking DB query in thread pool
    rows = await loop.run_in_executor(None, fetch_sessions, db)

    return [
        {
            "id": row["id"],
            "name": row["name"],
            "created_at": row["created_at"].isoformat()
            if hasattr(row["created_at"], "isoformat")
            else row["created_at"],
            "message_count": 0,
        }
        for row in rows
    ]
