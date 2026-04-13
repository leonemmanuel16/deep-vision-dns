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
    redis_host: str = "redis"
    redis_port: int = 6379

    # MinIO
    minio_host: str = "minio"
    minio_port: int = 9000
    minio_user: str = "minioadmin"
    minio_password: str = "changeme_minio_password"
    minio_bucket_snapshots: str = "snapshots"
    minio_bucket_clips: str = "clips"

    # DeepStream + YOLO
    yolo_model: str = "yolov8m"
    yolo_imgsz: int = 640
    confidence_threshold: float = 0.45
    tracker_type: str = "botsort.yaml"

    # DeepStream model paths
    onnx_model_path: str = "/opt/models/yolov8m.onnx"
    labels_path: str = "/opt/models/labels.txt"
    pgie_config_path: str = "/app/configs/pgie_yolo_config.txt"
    tracker_config_path: str = "/app/configs/tracker_config.yml"
    custom_parser_path: str = "/opt/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so"

    # Motion gate
    motion_on_threshold: float = 0.005
    motion_off_frames: int = 30
    detection_fps: int = 10

    # Processing
    process_every_n_frames: int = 3

    # Deduplication
    dedup_window_seconds: int = 30

    # Camera reconnection
    reconnect_interval: int = 30

    # Retention
    video_retention_hours: int = 48

    # Logging
    stats_interval_seconds: int = 60

    @property
    def db_url(self) -> str:
        return (
            f"postgresql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
        )

    @property
    def redis_url(self) -> str:
        return f"redis://{self.redis_host}:{self.redis_port}"

    @property
    def minio_endpoint(self) -> str:
        return f"{self.minio_host}:{self.minio_port}"

    class Config:
        env_file = ".env"


settings = Settings()
