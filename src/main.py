import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from config.database import Base, engine
# from model.tableModel import UserMemory,ChatMessage,UploadedPDF,Product,Sessions

from routes.route import router

# Load environment variables
load_dotenv()

# FastAPI app
app = FastAPI(debug=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)  # Include API routes


# Base.metadata.create_all(bind=engine)

def main():
    uvicorn.run("main:app", host="0.0.0.0", port=8888, reload=True)

if __name__ == "__main__":
    main()
