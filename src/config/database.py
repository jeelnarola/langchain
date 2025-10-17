import time
import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import pymysql
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ✅ Database configuration from environment variables
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_NAME = os.getenv("DB_NAME")

# ✅ SQLAlchemy connection URL
SQLALCHEMY_DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# ✅ Retry settings (useful if MySQL takes a few seconds to start)
MAX_RETRIES = 10
RETRY_DELAY = 3  # seconds

# ✅ Create SQLAlchemy engine with retry logic
engine = None
for attempt in range(1, MAX_RETRIES + 1):
    try:
        engine = create_engine(SQLALCHEMY_DATABASE_URL)
        # Test the connection
        with engine.connect() as conn:
            print(f"[SUCCESS] Connected to the database (attempt {attempt})")
        break
    except Exception as e:
        print(f"[WARNING] Attempt {attempt}: Could not connect to the database. Retrying in {RETRY_DELAY} seconds...")
        time.sleep(RETRY_DELAY)
else:
    raise Exception("[ERROR] Could not connect to the database after multiple attempts.")

# ✅ Create session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ✅ Base class for all SQLAlchemy models
Base = declarative_base()

# ✅ Dependency to get DB session (used inside FastAPI routes)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# database.py
# async def get_user_email_by_session(session_id: str) -> str:
#     """
#     Mock function to return a user's email by session_id.
#     Replace with real DB query in production.
#     """
#     # Example: return email for testing
#     return "user_email_from_db@example.com"