"""Detector configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Database
    db_host: str = "postgres"
    db_port: int = 5432
    db_name: str = "deepvision"
    db_user: str = "deepvision"
    db_password: str = "changeme_secure_password"

    # Redis
    redis_url: str = "redis://redis:6379"

    # MinIO
    minio_host: str = "minio"
    minio_port: int = 9000
    minio_user: str = "minioadmin"
    minio_password: str = "changeme_minio_password"
    minio_bucket_snapshots: str = "snapshots"
    minio_bucket_clips: str = "clips"

    # Detection
    detection_fps: int = 10
    confidence_threshold: float = 0.5
    motion_on_threshold: float = 0.005
    motion_off_frames: int = 30
    deepstream_model: str = "yolov8m"

    # Retention
    video_retention_hours: int = 48

    # Nightly
    nightly_start_hour: int = 0
    nightly_end_hour: int = 5

    @property
    def db_url(self) -> str:
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"

    class Config:
        env_file = ".env"


settings = Settings()
