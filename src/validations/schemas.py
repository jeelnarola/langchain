from pydantic import BaseModel
import json

class CreateSession(BaseModel):
    name: str = "New Chat"

class MessageIn(BaseModel):
    question: str  # this is a class

