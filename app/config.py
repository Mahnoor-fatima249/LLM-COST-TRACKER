from pydantic_settings import BaseSettings
from functools import lru_cache
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class Settings(BaseSettings):
    DATABASE_URL: str = f"sqlite+aiosqlite:///{os.path.join(BASE_DIR, 'llm_cost_tracker.db')}"
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7

    # --- Billing / Subscription (Stripe) ---
    STRIPE_SECRET_KEY: str = ""
    STRIPE_WEBHOOK_SECRET: str = ""
    APP_BASE_URL: str = "http://localhost:8000"
    DISABLE_BILLING: bool = True

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings():
    return Settings()
