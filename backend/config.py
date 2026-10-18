import os
import json
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

class Config:
    BASE_DIR = BASE_DIR
    ENV_PATH = ENV_PATH
    
    # Required API Keys
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    
    # Supabase (PostgreSQL + pgvector)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
    
    # Google Drive Integration
    GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1VDrNYA5GE6l9h21D2Co0HuuuD87Ain6d")
    
    # Networking
    HOST = os.getenv("HOST", "0.0.0.0")
    PORT = int(os.getenv("PORT", "8000"))
    
    # Storage Paths
    DATA_DIR = BASE_DIR / "data"
    UPLOADS_DIR = DATA_DIR / "uploads"
    CHUNKS_DIR = DATA_DIR / "chunks"

Config.DATA_DIR.mkdir(exist_ok=True, parents=True)
Config.UPLOADS_DIR.mkdir(exist_ok=True, parents=True)
Config.CHUNKS_DIR.mkdir(exist_ok=True, parents=True)

def reload_config():
    load_dotenv(ENV_PATH, override=True)
    Config.DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    Config.GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    Config.GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
    Config.SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    Config.SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
    Config.GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    Config.GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1VDrNYA5GE6l9h21D2Co0HuuuD87Ain6d")
