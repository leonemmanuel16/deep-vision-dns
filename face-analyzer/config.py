"""Face Analyzer microservice configuration."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "deepvision"
    db_user: str = "deepvision"
    db_password: str = "changeme_secure_password"

    # Redis
    redis_host: str = "redis"
    redis_port: int = 6379

    # MinIO
    minio_host: str = "minio"
    minio_port: int = 9000
    minio_user: str = "minioadmin"
    minio_password: str = "changeme_minio_password"
    minio_bucket_snapshots: str = "snapshots"

    # DeepFace settings
    face_detector_backend: str = "retinaface"
    face_recognition_model: str = "ArcFace"
    face_match_threshold: float = 0.40
    face_min_confidence: float = 0.25  # lowered for CCTV (was 0.5, too strict)
    face_min_size: int = 30  # minimum crop px (lowered for small/distant faces)
    face_analyze_attributes: bool = True
    face_log_level: str = "DEBUG"  # DEBUG to diagnose, INFO for production

    # Service
    service_port: int = 8002

    @property
    def db_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"

    class Config:
        env_file = ".env"


settings = Settings()
