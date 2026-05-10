"""
GovGuard™ — Application Configuration
Loads from AWS Secrets Manager in production, environment variables in development.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", case_sensitive=False)

    # Application
    ENVIRONMENT: str = "development"
    SECRET_KEY: str = "change-me-in-production-minimum-32-chars"
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000", "https://app.govguard.gov"]
    API_BASE_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://govguard:devpass@localhost:5432/govguard"
    DATABASE_POOL_SIZE: int = 20
    DATABASE_MAX_OVERFLOW: int = 10

    # Redis
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_RATE_LIMIT_DB: int = 1

    # AWS / Cognito
    AWS_REGION: str = "us-gov-west-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    COGNITO_USER_POOL_ID: str = "us-gov-west-1_XXXXXXXXX"
    COGNITO_CLIENT_ID: str = "your-cognito-client-id"
    COGNITO_CLIENT_SECRET: Optional[str] = None
    COGNITO_DOMAIN: str = "govguard.auth.us-gov-west-1.amazoncognito.com"

    # S3
    S3_EVIDENCE_BUCKET: str = "govguard-evidence-prod"
    S3_UPLOADS_BUCKET: str = "govguard-uploads-prod"
    S3_EXPORTS_BUCKET: str = "govguard-exports-prod"
    S3_ML_BUCKET: str = "govguard-ml-prod"
    KMS_KEY_ID: Optional[str] = None

    # OpenSearch
    OPENSEARCH_URL: str = "http://localhost:9200"
    OPENSEARCH_USERNAME: Optional[str] = None
    OPENSEARCH_PASSWORD: Optional[str] = None

    # Celery
    CELERY_BROKER_URL: str = "redis://localhost:6379/2"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/3"

    # Stripe
    STRIPE_SECRET_KEY: Optional[str] = None
    STRIPE_WEBHOOK_SECRET: Optional[str] = None
    STRIPE_PUBLISHABLE_KEY: Optional[str] = None

    # SAM.gov / Treasury DNP
    SAM_GOV_API_KEY: Optional[str] = None
    TREASURY_DNP_API_KEY: Optional[str] = None
    SAM_GOV_BASE_URL: str = "https://api.sam.gov/opportunities/v2"

    # Email (SES)
    SES_FROM_EMAIL: str = "noreply@govguard.gov"
    SES_FROM_NAME: str = "GovGuard Platform"

    # Rate Limiting
    RATE_LIMIT_PER_MINUTE: int = 1000
    RATE_LIMIT_BURST: int = 100

    # ML
    ML_MODEL_VERSION: str = "isolation_forest_v1.0.0"
    ML_FRAUD_THRESHOLD: float = 75.0

    # JWT
    JWT_ALGORITHM: str = "RS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 15

    # WebSocket
    WS_TOKEN_EXPIRE_SECONDS: int = 300

    @property
    def is_production(self) -> bool:
        return self.ENVIRONMENT == "production"

    @property
    def cognito_jwks_url(self) -> str:
        return (
            f"https://cognito-idp.{self.AWS_REGION}.amazonaws.com"
            f"/{self.COGNITO_USER_POOL_ID}/.well-known/jwks.json"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
