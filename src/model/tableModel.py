from fastapi import FastAPI
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey,BigInteger
from sqlalchemy.sql import func
from config.database import Base  # your declarative_base from earlier
from sqlalchemy.orm import relationship

class Sessions(Base):
    __tablename__ = "sessions"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    name = Column(String(255), default="New Chat")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    messages = relationship("ChatMessage", back_populates="session", cascade="all, delete-orphan")



class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"))
    role = Column(String(50), nullable=False)
    message = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("Sessions", back_populates="messages")

class UserMemory(Base):
    __tablename__ = "user_memory"

    id = Column(Integer, primary_key=True, autoincrement=True)
    field = Column(String(255), nullable=False)
    value = Column(String(255), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class UploadedPDF(Base):
    __tablename__ = "uploaded_pdfs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    filename = Column(String(255), nullable=False)
    vector_path = Column(String(500), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(255), nullable=False)
    description = Column(String(500))
    price = Column(Integer, nullable=False)
    category = Column(String(100), default="general")
    created_at = Column(DateTime(timezone=True), server_default=func.now())

