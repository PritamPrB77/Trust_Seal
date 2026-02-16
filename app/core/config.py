from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()

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
    
    # Database
    POSTGRES_SERVER: str = os.getenv("POSTGRES_SERVER", "localhost")
    POSTGRES_USER: str = os.getenv("POSTGRES_USER", "postgres")
    POSTGRES_PASSWORD: str = os.getenv("POSTGRES_PASSWORD", "postgres")
    POSTGRES_DB: str = os.getenv("POSTGRES_DB", "trustseal")
    POSTGRES_PORT: Optional[int] = os.getenv("POSTGRES_PORT", 5432)
    POSTGRES_SSLMODE: Optional[str] = os.getenv("POSTGRES_SSLMODE", "prefer")
    
    @property
    def DATABASE_URL(self) -> str:
        if self.POSTGRES_SSLMODE == "require":
            return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}?sslmode=require"
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def CORS_ORIGINS(self) -> List[str]:
        raw_origins = [origin.strip() for origin in self.BACKEND_CORS_ORIGINS.split(",")]
        return [origin for origin in raw_origins if origin]
    
    class Config:
        case_sensitive = True

settings = Settings()
