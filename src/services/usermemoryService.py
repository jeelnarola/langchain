from sqlalchemy.orm import Session
from model.tableModel import UserMemory
from typing import List

def fetch_latest_memory(db: Session, k: int = 5) -> str:
    """
    Retrieve the latest k user memory facts as formatted text.
    """
    rows = db.query(UserMemory).order_by(UserMemory.updated_at.desc()).limit(k).all()
    if not rows:
        return "No stored user memory."
    return "\n".join([f"{row.field}: {row.value}" for row in rows])


def save_memory(db: Session, field: str, value: str):
    """
    Save a user-related memory fact to the database.
    If the field already exists, update its value.
    """
    if not field or not value:
        return
    memory = db.query(UserMemory).filter(UserMemory.field == field).first()
    if memory:
        memory.value = value
    else:
        memory = UserMemory(field=field, value=value)
        db.add(memory)
    db.commit()
    db.refresh(memory)
    print(f"✅ Saved memory: {field} = {value}")
