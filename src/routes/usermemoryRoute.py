from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from config.database import get_db
from model.tableModel import UserMemory

memoryRouter = APIRouter()

@memoryRouter.get("/show")
def show_user_memory(db: Session = Depends(get_db)):
    """
    Show all stored user-related memory.
    """
    rows = db.query(UserMemory).order_by(UserMemory.updated_at.desc()).all()
    # Convert SQLAlchemy objects to dict
    result = [
        {"field": row.field, "value": row.value, "updated_at": row.updated_at}
        for row in rows
    ]
    return result
