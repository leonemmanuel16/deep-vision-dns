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

    # DeepStream + YOLO26
    force_yolo_fallback: bool = False  # Set FORCE_YOLO_FALLBACK=true to skip DeepStream
    deepstream_startup_timeout: int = 30  # seconds to wait before declaring DS dead
    yolo_model: str = "yolo26m"
    yolo_imgsz: int = 480  # 480 is optimal for CCTV on T1000 (was 640, too heavy)
    yolo_half_precision: bool = True  # FP16 — halves VRAM, faster inference on GPU
    confidence_threshold: float = 0.45
    tracker_type: str = "botsort.yaml"

    # DeepStream model paths
    onnx_model_path: str = "/opt/models/yolo26m.onnx"
    labels_path: str = "/opt/models/labels.txt"
    pgie_config_path: str = "/app/configs/pgie_yolo_config.txt"
    tracker_config_path: str = "/app/configs/tracker_config.yml"
    custom_parser_path: str = "/opt/DeepStream-Yolo/nvdsinfer_custom_impl_Yolo/libnvdsinfer_custom_impl_Yolo.so"

    # Motion gate
    motion_on_threshold: float = 0.005
    motion_off_frames: int = 30
    detection_fps: int = 10

    # Movement filter — only alert on moving objects
    movement_filter_enabled: bool = True
    # Minimum pixel displacement (bbox center) to consider an object "moving"
    movement_min_displacement: float = 30.0
    # Number of frames to track before deciding if object is stationary
    movement_history_frames: int = 10
    # Labels that require movement to trigger an alert (parked cars won't alert)
    movement_required_labels: str = "car,truck,bus,motorcycle,bicycle"
    # How long (seconds) to keep position history per tracker
    movement_history_ttl: float = 30.0

    # Face Recognition (via face-analyzer microservice)
    face_recognition_enabled: bool = True
    face_analyzer_url: str = "http://face-analyzer:8002"
    face_detector_backend: str = "retinaface"
    face_recognition_model: str = "ArcFace"
    face_match_threshold: float = 0.40  # cosine distance (lower = stricter)
    face_min_size: int = 40  # minimum crop size in pixels
    face_analyze_attributes: bool = True  # age, gender, emotion
    face_analyze_every_n: int = 5  # analyze face every N detections per tracker

    # Processing
    process_every_n_frames: int = 5  # analyze every 5th frame (was 3, reduced GPU load)

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
