"""API configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "deepvision"
    db_user: str = "deepvision"
    db_password: str = "changeme_secure_password"

    # JWT
    jwt_secret: str = "changeme_random_64_char_string"
    jwt_access_expire_minutes: int = 30
    jwt_refresh_expire_days: int = 7

    # Redis
    redis_url: str = "redis://redis:6379"

    # MinIO
    minio_host: str = "minio"
    minio_port: int = 9000
    minio_user: str = "minioadmin"
    minio_password: str = "changeme_minio_password"
    minio_bucket_snapshots: str = "snapshots"
    minio_bucket_clips: str = "clips"

    # Face Analyzer microservice
    face_analyzer_url: str = "http://face-analyzer:8002"

    # Alerts
    webhook_url: str = ""
    whatsapp_webhook_url: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_from: str = ""

    @property
    def database_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"

    class Config:
        env_file = ".env"


settings = Settings()
