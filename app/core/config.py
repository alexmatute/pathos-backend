from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import field_validator
from functools import lru_cache
from typing import List, Any
import json


class Settings(BaseSettings):
    APP_NAME: str = "PathOS"
    APP_ENV: str = "development"
    SECRET_KEY: str = "dev-secret-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    DATABASE_URL: str = "postgresql+asyncpg://pathos:pathos_pass@localhost:5432/pathos_db"
    DATABASE_URL_SYNC: str = "postgresql://pathos:pathos_pass@localhost:5432/pathos_db"

    REDIS_URL: str = "redis://localhost:6379/0"
    ANTHROPIC_API_KEY: str = ""

    # Storage: "gcs" (Google Cloud — recomendado) o "s3" (AWS)
    STORAGE_BACKEND: str = "gcs"

    # Google Cloud Storage
    GCS_BUCKET_NAME: str = "pathos-documents-prod"
    GCS_BUCKET_DEIDENTIFIED: str = "pathos-deidentified-dev"
    GCS_PROJECT_ID: str = ""
    GOOGLE_APPLICATION_CREDENTIALS: str = "/app/service-account.json"

    # AWS S3 (solo si STORAGE_BACKEND=s3)
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_REGION: str = "us-east-1"
    S3_BUCKET_NAME: str = "pathos-documents-prod"
    S3_BUCKET_DEIDENTIFIED: str = "pathos-deidentified-dev"

    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]
    EMBEDDING_MODEL: str = "sentence-transformers/all-mpnet-base-v2"
    EMBEDDING_DIM: int = 768

    ENABLE_OCR: bool = True
    ENABLE_PHI_DETECTION: bool = True
    ENABLE_AUTO_TAGGING: bool = True
    ENABLE_AUDIT_ALERTS: bool = True
    MAX_FILE_SIZE_MB: int = 50

    # pydantic-settings v2 style config (let docker-compose provide env vars)
    model_config = SettingsConfigDict(case_sensitive=True)

    # Accept either a JSON array (e.g. '["http://localhost:3000"]')
    # or a comma-separated string (e.g. 'http://a,http://b') for CORS origins.
    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def _parse_allowed_origins(cls, v: Any) -> List[str]:
        if v is None or v == "":
            return []
        if isinstance(v, list):
            return [str(s).strip() for s in v if str(s).strip()]
        if isinstance(v, str):
            s = v.strip()
            if not s:
                return []
            if s.startswith("["):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return [str(i).strip() for i in parsed if str(i).strip()]
                except Exception:
                    # fall back to comma-splitting if JSON parsing fails
                    pass
            return [part.strip() for part in s.split(",") if part.strip()]
        # As a last resort, cast to list[str]
        return [str(v)]


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
