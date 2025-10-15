from fastapi import APIRouter
from validations.schemas import CreateSession
from controllers.sessionController import get_session, api_create_session


sessionRouter = APIRouter()

@sessionRouter.get("/")
async def get_sessions():
    """
    Get all sessions.
    """
    return await get_session()

@sessionRouter.post("/add/")
async def create_session_route(data: CreateSession):
    """
    Create a new session.
    """
    return await api_create_session(data)


