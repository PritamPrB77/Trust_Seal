from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
load_dotenv(ROOT_DIR / ".env")

class Settings(BaseSettings):
    PROJECT_NAME: str = "TrustSeal IoT"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    VERIFICATION_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_MINUTES", "60"))
    BACKEND_CORS_ORIGINS: str = os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,https://trust-seal-tawny.vercel.app",
    )
    BACKEND_CORS_ORIGIN_REGEX: Optional[str] = os.getenv("BACKEND_CORS_ORIGIN_REGEX")
    DATABASE_URL_OVERRIDE: Optional[str] = os.getenv("DATABASE_URL")
    
    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "trustseal")
    POSTGRES_PORT: Optional[int] = os.getenv("POSTGRES_PORT", 5432)
    POSTGRES_SSLMODE: Optional[str] = os.getenv("POSTGRES_SSLMODE", "prefer")
    WS_REQUIRE_AUTH: bool = os.getenv("WS_REQUIRE_AUTH", "false").lower() == "true"
    REALTIME_QUEUE_MAXSIZE: int = int(os.getenv("REALTIME_QUEUE_MAXSIZE", "5000"))

    OPENROUTER_API_KEY: Optional[str] = os.getenv("OPENROUTER_API_KEY")
    OPENROUTER_BASE_URL: str = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku")
    OPENROUTER_TIMEOUT_SECONDS: int = int(os.getenv("OPENROUTER_TIMEOUT_SECONDS", "30"))
    OPENROUTER_MAX_TOKENS: int = int(os.getenv("OPENROUTER_MAX_TOKENS", "512"))
    OPENROUTER_SITE_URL: Optional[str] = os.getenv("OPENROUTER_SITE_URL")
    OPENROUTER_APP_NAME: str = os.getenv("OPENROUTER_APP_NAME", "TrustSeal IoT")
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        if self.POSTGRES_SSLMODE == "require":
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?sslmode=require"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        # Browser Origin header never has a trailing slash. Normalize to avoid false CORS mismatches.
        raw_origins = [origin.strip().rstrip("/") for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return [origin for origin in raw_origins if origin]
    
    class Config:
        case_sensitive = True

settings = Settings()
