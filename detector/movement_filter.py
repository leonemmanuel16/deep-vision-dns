"""
Movement Filter — Only alert on objects that are actually moving.

Tracks bbox center positions per tracker_id across frames.
Objects that remain stationary (like parked cars) are filtered out.
Objects that show displacement above the threshold generate alerts.

Persons and animals always generate alerts (no movement required).
"""

import math
import time
import logging
import threading
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Optional

from config import settings

logger = logging.getLogger(__name__)


@dataclass
class PositionRecord:
    """A single position observation for a tracked object."""
    cx: float  # bbox center x
    cy: float  # bbox center y
    timestamp: float


class MovementFilter:
    """
    Filters out stationary objects by tracking their bbox displacement.

    For each tracker_id, we store a history of bbox center positions.
    An object is considered "moving" if the total displacement from its
    first observed position exceeds `min_displacement` pixels.

    Labels NOT in `required_labels` (e.g., person, dog) always pass through.
    Labels IN `required_labels` (e.g., car, truck) must show movement.
    """

    def __init__(self):
        self.enabled = settings.movement_filter_enabled
        self.min_displacement = settings.movement_min_displacement
        self.history_frames = settings.movement_history_frames
        self.history_ttl = settings.movement_history_ttl

        # Labels that REQUIRE movement to generate an alert
        self.required_labels = set(
            l.strip() for l in settings.movement_required_labels.split(",") if l.strip()
        )

        # tracker_key -> deque of PositionRecord
        self._positions: dict[str, deque] = defaultdict(lambda: deque(maxlen=60))
        # tracker_key -> bool (True = confirmed moving)
        self._moving_confirmed: dict[str, bool] = {}
        self._lock = threading.Lock()
        self._last_cleanup = time.time()

        logger.info(
            f"MovementFilter initialized: enabled={self.enabled}, "
            f"min_displacement={self.min_displacement}px, "
            f"required_labels={self.required_labels}"
        )

    def update_position(self, camera_id: str, tracker_id: int,
                        bbox: dict, label: str) -> None:
        """
        Record a new position for a tracked object.
        Call this every frame for every detection.
        """
        if not self.enabled:
            return

        cx = (bbox["x1"] + bbox["x2"]) / 2.0
        cy = (bbox["y1"] + bbox["y2"]) / 2.0
        key = f"{camera_id}:{tracker_id}"
        now = time.time()

        with self._lock:
            self._positions[key].append(PositionRecord(cx=cx, cy=cy, timestamp=now))

            # Check if object is moving based on displacement
            positions = self._positions[key]
            if len(positions) >= 2:
                first = positions[0]
                last = positions[-1]
                displacement = math.hypot(last.cx - first.cx, last.cy - first.cy)

                if displacement >= self.min_displacement:
                    if key not in self._moving_confirmed or not self._moving_confirmed[key]:
                        logger.debug(
                            f"Object {key} ({label}) confirmed MOVING: "
                            f"displacement={displacement:.1f}px"
                        )
                    self._moving_confirmed[key] = True

        # Periodic cleanup
        if now - self._last_cleanup > 60:
            self._cleanup(now)

    def should_alert(self, camera_id: str, tracker_id: int, label: str) -> bool:
        """
        Decide if an alert/event should be created for this detection.

        Returns True if:
        - Movement filter is disabled, OR
        - Label does NOT require movement (e.g., person, animal), OR
        - Object has been confirmed as moving (displacement > threshold)

        Returns False if:
        - Label requires movement AND object is stationary
        """
        if not self.enabled:
            return True

        # Labels that don't require movement always pass
        if label not in self.required_labels:
            return True

        key = f"{camera_id}:{tracker_id}"
        with self._lock:
            # Check if we have enough observations
            positions = self._positions.get(key)
            if not positions or len(positions) < 2:
                # Not enough data yet — don't alert (wait for more frames)
                return False

            # Check if movement confirmed
            return self._moving_confirmed.get(key, False)

    def is_moving(self, camera_id: str, tracker_id: int) -> Optional[bool]:
        """
        Check if a tracked object is currently moving.
        Returns None if not enough data, True/False otherwise.
        """
        if not self.enabled:
            return True

        key = f"{camera_id}:{tracker_id}"
        with self._lock:
            positions = self._positions.get(key)
            if not positions or len(positions) < 2:
                return None
            return self._moving_confirmed.get(key, False)

    def _cleanup(self, now: float):
        """Remove stale tracker entries."""
        cutoff = now - self.history_ttl
        with self._lock:
            stale_keys = [
                key for key, positions in self._positions.items()
                if positions and positions[-1].timestamp < cutoff
            ]
            for key in stale_keys:
                del self._positions[key]
                self._moving_confirmed.pop(key, None)

            if stale_keys:
                logger.debug(f"MovementFilter cleanup: removed {len(stale_keys)} stale trackers")

        self._last_cleanup = now

    def get_stats(self) -> dict:
        """Return current filter statistics."""
        with self._lock:
            total_tracked = len(self._positions)
            moving = sum(1 for v in self._moving_confirmed.values() if v)
            stationary = total_tracked - moving
        return {
            "tracked_objects": total_tracked,
            "moving": moving,
            "stationary": stationary,
        }
