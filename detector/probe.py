"""
Probe Function — Extracts detection metadata from DeepStream batch.

Parses NvDsBatchMeta to extract:
- Bounding boxes (as percentage of frame)
- Labels and confidence
- Tracker IDs
- Zone/line crossing status
- Analytics metadata

Publishes events to Redis for real-time consumption.
"""

import json
import time
import logging
from typing import Optional

import redis

from config import settings
from deepstream_pipeline import YOLO_LABELS

logger = logging.getLogger(__name__)

try:
    import pyds
    PYDS_AVAILABLE = True
except ImportError:
    PYDS_AVAILABLE = False


class ProbeHandler:
    """Processes DeepStream batch metadata and publishes events."""

    def __init__(self):
        self.redis_client = redis.from_url(settings.redis_url)
        self._frame_count = 0

    def __call__(self, batch_meta, source_id_map: dict[str, int]):
        """
        Main probe callback — called for each batch of frames.
        Extracts detections and publishes to Redis.
        """
        if not PYDS_AVAILABLE:
            return

        # Reverse map: source_id → camera_id
        id_to_camera = {v: k for k, v in source_id_map.items()}

        frame_list = batch_meta.frame_meta_list
        while frame_list is not None:
            try:
                frame_meta = pyds.NvDsFrameMeta.cast(frame_list.data)
            except StopIteration:
                break

            source_id = frame_meta.source_id
            camera_id = id_to_camera.get(source_id, f"unknown_{source_id}")
            frame_width = frame_meta.source_frame_width
            frame_height = frame_meta.source_frame_height

            detections = []
            obj_list = frame_meta.obj_meta_list

            while obj_list is not None:
                try:
                    obj_meta = pyds.NvDsObjectMeta.cast(obj_list.data)
                except StopIteration:
                    break

                # Skip low-confidence detections
                if obj_meta.confidence < settings.confidence_threshold:
                    try:
                        obj_list = obj_list.next
                    except StopIteration:
                        break
                    continue

                # Extract bbox as percentages
                rect = obj_meta.rect_params
                bbox = {
                    "x1": round(rect.left / frame_width, 4),
                    "y1": round(rect.top / frame_height, 4),
                    "x2": round((rect.left + rect.width) / frame_width, 4),
                    "y2": round((rect.top + rect.height) / frame_height, 4),
                }

                # Get label
                class_id = obj_meta.class_id
                label = YOLO_LABELS[class_id] if class_id < len(YOLO_LABELS) else f"class_{class_id}"

                # Get tracker ID
                tracker_id = obj_meta.object_id

                # Get analytics metadata (zone status)
                zone_status = self._get_analytics_meta(obj_meta)

                detection = {
                    "camera_id": camera_id,
                    "label": label,
                    "class_id": class_id,
                    "confidence": round(obj_meta.confidence, 3),
                    "bbox": bbox,
                    "tracker_id": int(tracker_id),
                    "zone_status": zone_status,
                    "timestamp": time.time(),
                }
                detections.append(detection)

                try:
                    obj_list = obj_list.next
                except StopIteration:
                    break

            # Publish detections to Redis
            if detections:
                self._publish_detections(camera_id, detections)

            try:
                frame_list = frame_list.next
            except StopIteration:
                break

        self._frame_count += 1

    def _get_analytics_meta(self, obj_meta) -> dict:
        """Extract nvdsanalytics metadata from object."""
        status = {}
        if not PYDS_AVAILABLE:
            return status

        try:
            user_meta_list = obj_meta.obj_user_meta_list
            while user_meta_list is not None:
                user_meta = pyds.NvDsUserMeta.cast(user_meta_list.data)
                if user_meta.base_meta.meta_type == pyds.NvDsMetaType.NVDS_ANALYTICS_OBJ_INFO_META:
                    analytics_meta = pyds.NvDsAnalyticsObjInfo.cast(user_meta.user_meta_data)
                    status["roi"] = list(analytics_meta.roiStatus) if analytics_meta.roiStatus else []
                    status["lc"] = list(analytics_meta.lcStatus) if analytics_meta.lcStatus else []
                    status["dir"] = analytics_meta.dirStatus if hasattr(analytics_meta, "dirStatus") else ""
                try:
                    user_meta_list = user_meta_list.next
                except StopIteration:
                    break
        except Exception:
            pass

        return status

    def _publish_detections(self, camera_id: str, detections: list[dict]):
        """Publish detections to Redis channels."""
        payload = json.dumps({
            "camera_id": camera_id,
            "detections": detections,
            "frame_number": self._frame_count,
            "timestamp": time.time(),
        })

        # Publish to camera-specific channel
        self.redis_client.publish(f"detections:{camera_id}", payload)

        # Publish to global channel
        self.redis_client.publish("detections:all", payload)

        # Add to Redis Stream for persistence
        self.redis_client.xadd(
            "stream:detections",
            {"data": payload},
            maxlen=10000,
        )

    def publish_event(self, event: dict):
        """Publish a validated event (after best-shot selection)."""
        payload = json.dumps(event)
        self.redis_client.publish("events:new", payload)
        self.redis_client.xadd(
            "stream:events",
            {"data": payload},
            maxlen=50000,
        )
