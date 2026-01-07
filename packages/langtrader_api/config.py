"""
Configuration management using Pydantic Settings
"""
from pydantic_settings import BaseSettings
from pydantic import field_validator
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
    
    @field_validator("API_KEYS", "CORS_ORIGINS", mode="before")
    @classmethod
    def parse_comma_separated(cls, v):
        """Parse comma-separated string into list"""
        if isinstance(v, str):
            return [x.strip() for x in v.split(",") if x.strip()]
        return v
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": True,
    }


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance"""
    return Settings()


settings = get_settings()

