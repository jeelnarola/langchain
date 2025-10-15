from fastapi import APIRouter
from validations.schemas import MessageIn
from sqlalchemy.orm import Session
from config.database import get_db
from fastapi import Depends
from controllers.askControllers import ask_in_session

askRouter = APIRouter() 

@askRouter.get("/")
async def ask_home():
    return {"message": "Ask home endpoint"}


@askRouter.post("/{session_id}/")
async def ask_question_in_session(session_id: str, data: MessageIn,db: Session = Depends(get_db)):
    """
    Ask a question in a given session using the global vectorstore.
    """
    #  {"message":"Done Ask...",session_id: session_id, "question": data.q}
    return await ask_in_session(session_id, data,db)
