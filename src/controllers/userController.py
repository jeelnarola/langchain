from fastapi import HTTPException
from pydantic import BaseModel

class UserResponse(BaseModel):
    id: int
    name: str
    email: str

async def get_user(user_id: int):
    """Get user by ID"""
    if user_id <= 0:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # Mock user data
    return UserResponse(
        id=user_id,
        name=f"User {user_id}",
        email=f"user{user_id}@example.com"
    )

async def create_user(name: str, email: str):
    """Create new user"""
    if not name or not email:
        raise HTTPException(status_code=400, detail="Name and email required")
    
    # Mock creation
    return UserResponse(
        id=123,
        name=name,
        email=email
    )