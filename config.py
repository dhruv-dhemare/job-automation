"""Environment-backed configuration for the personal internship assistant."""

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Settings:
    search_api_key: str = os.getenv("SEARCH_API_KEY", "")
    search_provider: str = os.getenv("SEARCH_PROVIDER", "tavily")
    search_api_url: str = os.getenv("SEARCH_API_URL", "https://api.tavily.com/search")
    resume_path: Path = Path(os.getenv("RESUME_PATH", str(BASE_DIR / "data" / "resume.pdf")))
    database_path: Path = Path(os.getenv("DATABASE_PATH", str(BASE_DIR / "data" / "internship_tracker.db")))
    anthropic_api_key: str = os.getenv("ANTHROPIC_API_KEY", "")
    claude_model: str = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-5")
    ai_provider: str = os.getenv("AI_PROVIDER", "gemini")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    ollama_url: str = os.getenv("OLLAMA_URL", "http://localhost:11434/api/generate")
    ollama_model: str = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
    hunter_api_key: str = os.getenv("HUNTER_API_KEY", "")
    google_client_secret: Path = Path(os.getenv("GOOGLE_CLIENT_SECRET_FILE", str(BASE_DIR / "credentials.json")))
    google_token: Path = Path(os.getenv("GOOGLE_TOKEN_FILE", str(BASE_DIR / "token.json")))


settings = Settings()
