from pydantic import BaseModel, validator, Field
from typing import Optional

class ChatRequest(BaseModel):
    """Validation schema for chat requests"""
    chat_id: str = Field(..., min_length=1, max_length=100)
    message: str = Field(..., min_length=1, max_length=10000)
    
    @validator('chat_id')
    def chat_id_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('chat_id cannot be empty')
        return v.strip()
    
    @validator('message')
    def message_valid(cls, v):
        if not v or not v.strip():
            raise ValueError('Message cannot be empty')
        if len(v) > 10000:
            raise ValueError('Message too long (max 10000 characters)')
        return v.strip()

class ChatResponse(BaseModel):
    """Response schema for chat"""
    reply: str
    
class DocumentUploadResponse(BaseModel):
    """Response schema for document upload"""
    filename: str
    chunks_added: Optional[int] = None
    error: Optional[str] = None
