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


settings = Settings()
