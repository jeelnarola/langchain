from sqlalchemy.orm import Session
from model.tableModel import Sessions as SessionModel
from typing import List, Dict

def fetch_sessions(db: Session) -> List[Dict]:
    """
    Fetch all sessions, most recent first.
    """
    sessions = db.query(SessionModel).order_by(SessionModel.created_at.desc()).all()
    return [
        {"id": session.id, "name": session.name, "created_at": session.created_at}
        for session in sessions
    ]


def insert_session(db: Session, name: str) -> SessionModel:
    """
    Insert a new session into the database.
    """
    new_session = SessionModel(name=name)
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


def update_session_name(db: Session, session_id: int, name: str) -> bool:
    """
    Update the session name in the database.
    Returns True if updated, False if session not found.
    """
    session_obj = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    if session_obj:
        session_obj.name = name
        db.commit()
        return True
    return False
