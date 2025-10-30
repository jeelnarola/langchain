import sys
import os
import json
import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.database import Base, engine
from model.tableModel import UserMemory, ChatMessage, UploadedPDF, Product, Sessions
from routes.route import router

# Load environment variables
load_dotenv()

# ✅ Create a single FastAPI instance
app = FastAPI(title="Telegram + LLM API Server")

# ✅ Middleware for CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ✅ Health check endpoint
@app.get("/gethealth")
def get_health():
    return {"status": "ok", "message": "API is healthy"}

# ✅ Include all routes
app.include_router(router)

# ✅ Initialize DB
Base.metadata.create_all(bind=engine)

# ✅ Entry point
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=True)
