from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()

BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOADS_DIR = DATA_DIR / "uploads"
BOOKS_DIR = DATA_DIR / "books"
DB_PATH = DATA_DIR / "app.db"

DATA_DIR.mkdir(exist_ok=True)
UPLOADS_DIR.mkdir(exist_ok=True)
BOOKS_DIR.mkdir(exist_ok=True)


class Settings:
    deepseek_api_key: str = os.getenv("DEEPSEEK_API_KEY", "")
    deepseek_model: str = os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash")
    deepseek_base_url: str = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    dehydrate_concurrency: int = int(os.getenv("DEHYDRATE_CONCURRENCY", "20"))
    max_retries: int = int(os.getenv("MAX_RETRIES", "3"))
    chunk_char_limit: int = int(os.getenv("CHUNK_CHAR_LIMIT", "12000"))


settings = Settings()
