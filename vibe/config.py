import os
from dataclasses import dataclass
try:
    from dotenv import load_dotenv
except Exception:
    def load_dotenv():
        return None

load_dotenv()


@dataclass
class Settings:
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_API_URL: str = os.getenv("GROQ_API_URL", "")
    MONGO_URI: str = os.getenv("MONGO_URI", "")
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    OPENAI_API_URL: str = os.getenv("OPENAI_API_URL", "")
    OPENAI_MODEL: str = os.getenv("OPENAI_MODEL", "openai/gpt-oss-20b")
    CHROMA_DB_PATH: str = os.getenv("CHROMA_DB_PATH", "./chroma_db")
    MODEL_CACHE_PATH: str = os.getenv("MODEL_CACHE_PATH", "./model_cache")
    STREAMLIT_SERVER_PORT: int = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))
    VOICE_AUTOPLAY: bool = os.getenv("VOICE_AUTOPLAY", "true").lower() in ("1", "true", "yes")
    # Default offline behavior; if true the app will start in offline mode unless overridden
    OFFLINE_DEFAULT: bool = os.getenv("OFFLINE_DEFAULT", "false").lower() in ("1", "true", "yes")


settings = Settings()
