import os
from pathlib import Path
from dotenv import load_dotenv

# Base Directory
BASE_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = BASE_DIR / ".env"

load_dotenv(ENV_PATH)

class Config:
    BASE_DIR = BASE_DIR
    ENV_PATH = ENV_PATH
    DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY", "")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
    HOST = os.getenv("HOST", "127.0.0.1")
    PORT = int(os.getenv("PORT", "8000"))
    
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
    Config.SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    Config.SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
