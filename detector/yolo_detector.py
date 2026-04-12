"""
YOLO Detector — GPU-accelerated object detection using Ultralytics YOLOv8.

Loads YOLOv8n (nano) for fast inference on NVIDIA GPUs.
Uses BoT-SORT tracker for multi-object tracking across frames.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import torch
from ultralytics import YOLO

from config import settings

logger = logging.getLogger(__name__)

# COCO labels that map to event types
PERSON_LABELS = {"person"}
VEHICLE_LABELS = {"car", "truck", "bus", "motorcycle", "bicycle"}
ANIMAL_LABELS = {"cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}


def classify_event_type(label: str) -> str:
    """Map a COCO label to an event type."""
    if label in PERSON_LABELS:
        return "person_detected"
    elif label in VEHICLE_LABELS:
        return "vehicle_detected"
    elif label in ANIMAL_LABELS:
        return "animal_detected"
    return "object_detected"


# Labels we care about for generating events
EVENT_LABELS = PERSON_LABELS | VEHICLE_LABELS | ANIMAL_LABELS


@dataclass
class Detection:
    """A single detection result."""
    label: str
    confidence: float
    bbox: dict  # {"x1": float, "y1": float, "x2": float, "y2": float}
    tracker_id: Optional[int] = None
    event_type: str = ""

    def __post_init__(self):
        if not self.event_type:
            self.event_type = classify_event_type(self.label)


class YOLODetector:
    """YOLOv8 detector with GPU inference and built-in tracking."""

    def __init__(self):
        self.device = self._select_device()
        logger.info(f"Loading YOLO model: {settings.yolo_model} on device: {self.device}")

        self.model = YOLO(settings.yolo_model)
        self.model.to(self.device)

        # Get class names from the model
        self.class_names = self.model.names  # {0: 'person', 1: 'bicycle', ...}

        logger.info(
            f"YOLO model loaded — {len(self.class_names)} classes, "
            f"device={self.device}, imgsz={settings.yolo_imgsz}"
        )

    @staticmethod
    def _select_device() -> str:
        """Select the best available device."""
        if torch.cuda.is_available():
            gpu_name = torch.cuda.get_device_name(0)
            vram = torch.cuda.get_device_properties(0).total_memory / (1024 ** 3)
            logger.info(f"CUDA available: {gpu_name} ({vram:.1f} GB)")
            return "cuda:0"
        logger.warning("CUDA not available — falling back to CPU (slow)")
        return "cpu"

    def detect(self, frame: np.ndarray, use_tracker: bool = True) -> list[Detection]:
        """
        Run detection (and optionally tracking) on a single frame.

        Args:
            frame: BGR numpy array from OpenCV
            use_tracker: If True, use BoT-SORT tracking for persistent IDs

        Returns:
            List of Detection objects filtered by confidence threshold
        """
        if frame is None or frame.size == 0:
            return []

        try:
            if use_tracker:
                results = self.model.track(
                    frame,
                    imgsz=settings.yolo_imgsz,
                    conf=settings.confidence_threshold,
                    device=self.device,
                    tracker=settings.tracker_type,
                    persist=True,
                    verbose=False,
                )
            else:
                results = self.model(
                    frame,
                    imgsz=settings.yolo_imgsz,
                    conf=settings.confidence_threshold,
                    device=self.device,
                    verbose=False,
                )
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return []

        detections = []
        for result in results:
            boxes = result.boxes
            if boxes is None or len(boxes) == 0:
                continue

            for i in range(len(boxes)):
                cls_id = int(boxes.cls[i].item())
                label = self.class_names.get(cls_id, f"class_{cls_id}")
                conf = float(boxes.conf[i].item())

                # Only keep labels we care about
                if label not in EVENT_LABELS:
                    continue

                x1, y1, x2, y2 = boxes.xyxy[i].tolist()
                bbox = {
                    "x1": round(x1, 1),
                    "y1": round(y1, 1),
                    "x2": round(x2, 1),
                    "y2": round(y2, 1),
                }

                tracker_id = None
                if use_tracker and boxes.id is not None:
                    tracker_id = int(boxes.id[i].item())

                detections.append(Detection(
                    label=label,
                    confidence=round(conf, 4),
                    bbox=bbox,
                    tracker_id=tracker_id,
                ))

        return detections
