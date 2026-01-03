"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from typing import List, Optional
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables"""
    
    # Application
    APP_NAME: str = "LangTrader API"
    DEBUG: bool = False
    ENVIRONMENT: str = "development"
    
    # Database
    DATABASE_URL: str
    
    # Security
    API_KEYS: List[str] = ["dev-key-123"]
    SECRET_KEY: str = "change-me-in-production"
    
    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
    ]
    
    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 120
    
    # Bot Management
    BOT_SCRIPT_PATH: str = "examples/run_once.py"
    
    # Optional: Redis
    REDIS_URL: Optional[str] = None
    
    # Optional: LangSmith
    LANGSMITH_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Parse comma-separated lists
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str):
            if field_name in ("API_KEYS", "CORS_ORIGINS"):
                return [x.strip() for x in raw_val.split(",") if x.strip()]
            return raw_val


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

