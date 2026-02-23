from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from pathlib import Path
from urllib.parse import quote_plus
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
# In local development we want backend/.env to win over stale shell variables.
load_dotenv(ROOT_DIR / ".env", override=True)

class Settings(BaseSettings):
    PROJECT_NAME: str = "TrustSeal IoT"
    API_V1_STR: str = "/api/v1"
    SECRET_KEY: str = os.getenv("SECRET_KEY", "your-secret-key-here-change-in-production")
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    VERIFICATION_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("VERIFICATION_TOKEN_EXPIRE_MINUTES", "60"))
    BACKEND_CORS_ORIGINS: str = os.getenv(
        "BACKEND_CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    )
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
    OPENROUTER_EMBEDDING_MODEL: str = os.getenv(
        "OPENROUTER_EMBEDDING_MODEL", "openai/text-embedding-3-small"
    )
    OPENROUTER_SITE_URL: Optional[str] = os.getenv("OPENROUTER_SITE_URL")
    OPENROUTER_APP_NAME: str = os.getenv("OPENROUTER_APP_NAME", "TrustSeal IoT")
    RAG_TOP_K: int = int(os.getenv("RAG_TOP_K", "10"))
    RAG_EMBEDDING_DIM: int = int(os.getenv("RAG_EMBEDDING_DIM", "256"))
    RAG_MAX_SENSOR_LOG_DOCS: int = int(os.getenv("RAG_MAX_SENSOR_LOG_DOCS", "500"))
    RAG_MAX_CUSTODY_DOCS: int = int(os.getenv("RAG_MAX_CUSTODY_DOCS", "300"))
    RAG_REQUIRE_PGVECTOR: bool = os.getenv("RAG_REQUIRE_PGVECTOR", "true").lower() == "true"
    RAG_USE_OPENROUTER_EMBEDDINGS: bool = (
        os.getenv("RAG_USE_OPENROUTER_EMBEDDINGS", "true").lower() == "true"
    )
    SOC_AGENT_MODEL: str = os.getenv("SOC_AGENT_MODEL", os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-haiku"))
    SOC_AGENT_TIMEOUT_SECONDS: int = int(os.getenv("SOC_AGENT_TIMEOUT_SECONDS", "45"))
    SOC_AGENT_MAX_ITERATIONS: int = int(os.getenv("SOC_AGENT_MAX_ITERATIONS", "8"))
    SOC_AGENT_TOP_K: int = int(os.getenv("SOC_AGENT_TOP_K", "8"))
    SOC_AGENT_BASELINE_WINDOW: int = int(os.getenv("SOC_AGENT_BASELINE_WINDOW", "200"))
    SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS: int = int(os.getenv("SOC_AGENT_STREAM_TOOL_OUTPUT_CHARS", "500"))
    SOC_AGENT_INCIDENT_SEARCH_LIMIT: int = int(os.getenv("SOC_AGENT_INCIDENT_SEARCH_LIMIT", "5"))
    DB_CONNECT_TIMEOUT_SECONDS: int = int(os.getenv("DB_CONNECT_TIMEOUT_SECONDS", "8"))
    DB_POOL_TIMEOUT_SECONDS: int = int(os.getenv("DB_POOL_TIMEOUT_SECONDS", "15"))
    DB_POOL_RECYCLE_SECONDS: int = int(os.getenv("DB_POOL_RECYCLE_SECONDS", "1800"))
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_OVERRIDE:
            return self.DATABASE_URL_OVERRIDE
        encoded_user = quote_plus(str(self.POSTGRES_USER))
        encoded_password = quote_plus(str(self.POSTGRES_PASSWORD))
        if self.POSTGRES_SSLMODE == "require":
            return (
                f"postgresql://{encoded_user}:{encoded_password}@"
                f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?sslmode=require"
            )
        return (
            f"postgresql://{encoded_user}:{encoded_password}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw_origins = [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return [origin for origin in raw_origins if origin]
    
    class Config:
        case_sensitive = True

settings = Settings()
