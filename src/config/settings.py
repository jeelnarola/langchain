# Configuration settings for the application
import os
from dotenv import load_dotenv

load_dotenv()

# API Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1000"))
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))

# Agent Configuration
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "10"))
MAX_HISTORY_MESSAGES = int(os.getenv("MAX_HISTORY_MESSAGES", "8"))
MAX_RETRY_ATTEMPTS = int(os.getenv("MAX_RETRY_ATTEMPTS", "3"))
RETRY_DELAY = int(os.getenv("RETRY_DELAY", "2"))

# Memory Configuration
MEM0_KEY = os.getenv("MEM0_KEY")
MAX_MEMORY_ITEMS = int(os.getenv("MAX_MEMORY_ITEMS", "5"))

# Vector Store Configuration
VECTOR_SEARCH_K = int(os.getenv("VECTOR_SEARCH_K", "3"))
MAX_CONTEXT_DOCS = int(os.getenv("MAX_CONTEXT_DOCS", "5"))

# SMTP Configuration
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")
