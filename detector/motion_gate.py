"""
Motion Gate — CPU-based motion detection with hysteresis.

For each camera, grabs sub-stream frames at ~10 FPS, computes motion area
via frame differencing, and decides if the camera is ACTIVE or IDLE.
Only ACTIVE cameras get sent to the GPU (DeepStream).
"""

import cv2
import numpy as np
import threading
import time
import logging
from dataclasses import dataclass, field
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class CameraMotionState:
    """Tracks motion state for a single camera."""
    camera_id: str
    rtsp_url: str
    is_active: bool = False
    idle_frame_count: int = 0
    prev_gray: Optional[np.ndarray] = None
    motion_area_pct: float = 0.0
    last_update: float = field(default_factory=time.time)


class MotionGate:
    """
    Monitors multiple RTSP streams for motion using CPU-only processing.
    Returns list of camera IDs with real activity so DeepStream only
    processes cameras that need GPU inference.
    """

    def __init__(
        self,
        on_threshold: float = None,
        off_frames: int = None,
        target_fps: int = None,
    ):
        self.on_threshold = on_threshold or settings.motion_on_threshold
        self.off_frames = off_frames or settings.motion_off_frames
        self.target_fps = target_fps or settings.detection_fps
        self.cameras: dict[str, CameraMotionState] = {}
        self.captures: dict[str, cv2.VideoCapture] = {}
        self._lock = threading.Lock()
        self._running = False
        self._threads: list[threading.Thread] = []

    def add_camera(self, camera_id: str, rtsp_sub_url: str):
        """Register a camera for motion monitoring."""
        with self._lock:
            self.cameras[camera_id] = CameraMotionState(
                camera_id=camera_id,
                rtsp_url=rtsp_sub_url,
            )
        logger.info(f"Motion gate: added camera {camera_id}")

    def remove_camera(self, camera_id: str):
        """Remove a camera from monitoring."""
        with self._lock:
            self.cameras.pop(camera_id, None)
            cap = self.captures.pop(camera_id, None)
            if cap:
                cap.release()
        logger.info(f"Motion gate: removed camera {camera_id}")

    def get_active_cameras(self) -> list[str]:
        """Return list of camera IDs currently showing motion."""
        with self._lock:
            return [
                cam_id for cam_id, state in self.cameras.items()
                if state.is_active
            ]

    def get_all_states(self) -> dict[str, dict]:
        """Return motion state for all cameras."""
        with self._lock:
            return {
                cam_id: {
                    "is_active": state.is_active,
                    "motion_area_pct": round(state.motion_area_pct, 4),
                    "idle_frame_count": state.idle_frame_count,
                }
                for cam_id, state in self.cameras.items()
            }

    def _connect(self, camera_id: str) -> Optional[cv2.VideoCapture]:
        """Open RTSP connection for a camera."""
        state = self.cameras.get(camera_id)
        if not state:
            return None

        cap = cv2.VideoCapture(state.rtsp_url, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)

        if not cap.isOpened():
            logger.warning(f"Motion gate: cannot connect to {camera_id} at {state.rtsp_url}")
            return None

        self.captures[camera_id] = cap
        logger.info(f"Motion gate: connected to {camera_id}")
        return cap

    def _compute_motion(self, camera_id: str, frame: np.ndarray) -> float:
        """
        Compute motion area percentage using frame differencing.
        Returns: fraction of frame area with motion (0.0 - 1.0)
        """
        state = self.cameras[camera_id]

        # Resize to 640x360 for efficiency
        small = cv2.resize(frame, (640, 360))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0)

        if state.prev_gray is None:
            state.prev_gray = gray
            return 0.0

        # Frame difference
        delta = cv2.absdiff(state.prev_gray, gray)
        state.prev_gray = gray

        # Threshold
        thresh = cv2.threshold(delta, 25, 255, cv2.THRESH_BINARY)[1]
        thresh = cv2.dilate(thresh, None, iterations=2)

        # Find contours and compute total motion area
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        motion_area = sum(cv2.contourArea(c) for c in contours)
        total_area = 640 * 360

        return motion_area / total_area

    def _update_state(self, camera_id: str, motion_pct: float):
        """Apply hysteresis logic to determine active/idle state."""
        state = self.cameras[camera_id]
        state.motion_area_pct = motion_pct
        state.last_update = time.time()

        if motion_pct > self.on_threshold:
            # Motion detected — activate immediately
            if not state.is_active:
                logger.info(f"Camera {camera_id}: ACTIVE (motion={motion_pct:.3%})")
            state.is_active = True
            state.idle_frame_count = 0
        else:
            # No motion — count idle frames before deactivating
            state.idle_frame_count += 1
            if state.idle_frame_count >= self.off_frames:
                if state.is_active:
                    logger.info(f"Camera {camera_id}: IDLE (no motion for {self.off_frames} frames)")
                state.is_active = False

    def _monitor_camera(self, camera_id: str):
        """Monitor loop for a single camera (runs in its own thread)."""
        frame_interval = 1.0 / self.target_fps
        reconnect_delay = 5.0

        while self._running:
            cap = self.captures.get(camera_id) or self._connect(camera_id)
            if not cap:
                time.sleep(reconnect_delay)
                continue

            try:
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Camera {camera_id}: frame read failed, reconnecting...")
                    cap.release()
                    self.captures.pop(camera_id, None)
                    time.sleep(reconnect_delay)
                    continue

                motion_pct = self._compute_motion(camera_id, frame)
                with self._lock:
                    self._update_state(camera_id, motion_pct)

                time.sleep(frame_interval)

            except Exception as e:
                logger.error(f"Camera {camera_id}: error in motion loop: {e}")
                cap.release()
                self.captures.pop(camera_id, None)
                time.sleep(reconnect_delay)

    def start(self):
        """Start motion monitoring for all registered cameras."""
        self._running = True
        for camera_id in list(self.cameras.keys()):
            t = threading.Thread(
                target=self._monitor_camera,
                args=(camera_id,),
                daemon=True,
                name=f"motion-{camera_id[:8]}",
            )
            t.start()
            self._threads.append(t)
        logger.info(f"Motion gate started for {len(self.cameras)} cameras")

    def stop(self):
        """Stop all monitoring threads."""
        self._running = False
        for cap in self.captures.values():
            cap.release()
        self.captures.clear()
        logger.info("Motion gate stopped")
