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
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
    
    # Supabase (PostgreSQL + pgvector)
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_KEY", "")
    
    # Google Drive Integration
    GOOGLE_CREDENTIALS_JSON = os.getenv("GOOGLE_CREDENTIALS_JSON", "")
    if not GOOGLE_CREDENTIALS_JSON and (BASE_DIR / "service_account.json").exists():
        try:
            GOOGLE_CREDENTIALS_JSON = (BASE_DIR / "service_account.json").read_text(encoding="utf-8")
        except Exception:
            pass
    GOOGLE_DRIVE_FOLDER_ID = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "1VDrNYA5GE6l9h21D2Co0HuuuD87Ain6d")
    GOOGLE_OAUTH_ACCESS_TOKEN = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "")
    GOOGLE_OAUTH_REFRESH_TOKEN = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "") or os.getenv("GOOGLE_ADMIN_REFRESH_TOKEN", "")
    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "") or os.getenv("GOOGLE_ADMIN_CLIENT_ID", "")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "") or os.getenv("GOOGLE_ADMIN_CLIENT_SECRET", "")
    
    # Production & Security Controls
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
    READONLY_CONFIG = os.getenv("READONLY_CONFIG", "false").lower() in ("true", "1", "yes")
    CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    MAX_RESOURCE_SIZE_MB = int(os.getenv("MAX_RESOURCE_SIZE_MB", "50"))

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
    Config.GOOGLE_OAUTH_ACCESS_TOKEN = os.getenv("GOOGLE_OAUTH_ACCESS_TOKEN", "")
    Config.GOOGLE_OAUTH_REFRESH_TOKEN = os.getenv("GOOGLE_OAUTH_REFRESH_TOKEN", "") or os.getenv("GOOGLE_ADMIN_REFRESH_TOKEN", "")
    Config.GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "") or os.getenv("GOOGLE_ADMIN_CLIENT_ID", "")
    Config.GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "") or os.getenv("GOOGLE_ADMIN_CLIENT_SECRET", "")
    Config.ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()
    Config.ADMIN_API_KEY = os.getenv("ADMIN_API_KEY", "")
    Config.READONLY_CONFIG = os.getenv("READONLY_CONFIG", "false").lower() in ("true", "1", "yes")
    Config.CORS_ORIGINS = [o.strip() for o in os.getenv("CORS_ORIGINS", "*").split(",") if o.strip()]
    Config.MAX_UPLOAD_SIZE_MB = int(os.getenv("MAX_UPLOAD_SIZE_MB", "500"))
    Config.MAX_RESOURCE_SIZE_MB = int(os.getenv("MAX_RESOURCE_SIZE_MB", "50"))
    if not Config.GOOGLE_CREDENTIALS_JSON and (Config.BASE_DIR / "service_account.json").exists():
        try:
            Config.GOOGLE_CREDENTIALS_JSON = (Config.BASE_DIR / "service_account.json").read_text(encoding="utf-8")
        except Exception:
            pass
