"""
Deep Vision by DNS — Detector Service

Main entry point that orchestrates:
1. Motion Gate (CPU) — monitors all cameras for movement
2. Grid Selector — decides optimal GPU batch layout
3. DeepStream Pipeline — GPU inference on active cameras only
4. Best Shot + Event Logic — validates and stores events
5. Nightly Job — deep review scheduler
"""

import time
import signal
import logging
import threading

import schedule

from config import settings
from motion_gate import MotionGate
from grid_selector import GridSelector
from deepstream_pipeline import DeepStreamPipeline, DEEPSTREAM_AVAILABLE
from probe import ProbeHandler
from best_shot import BestShotSelector
from event_logic import EventManager
from nightly_job import NightlyReview

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("detector")


class DetectorService:
    """Main detector service orchestrating all components."""

    POLL_INTERVAL = 2.0  # seconds between motion gate checks

    def __init__(self):
        self.motion_gate = MotionGate()
        self.grid_selector = GridSelector()
        self.probe_handler = ProbeHandler()
        self.best_shot = BestShotSelector()
        self.event_manager = EventManager()
        self.nightly = NightlyReview()

        self.pipeline = DeepStreamPipeline(probe_callback=self.probe_handler)

        self._running = False
        self._current_grid = None

    def _load_cameras(self):
        """Load cameras from database and register with motion gate."""
        cameras = self.event_manager.get_camera_rtsp_urls()
        logger.info(f"Loaded {len(cameras)} cameras from database")

        for cam_id, cam_data in cameras.items():
            sub_url = cam_data.get("rtsp_sub_url", cam_data["rtsp_url"])
            self.motion_gate.add_camera(cam_id, sub_url)
            self.event_manager.update_camera_status(cam_id, "online")

    def _orchestration_loop(self):
        """
        Main loop: checks motion gate → updates DeepStream sources.
        Runs every POLL_INTERVAL seconds.
        """
        while self._running:
            try:
                active_ids = self.motion_gate.get_active_cameras()
                num_active = len(active_ids)

                # Get grid config
                grid = self.grid_selector.select(num_active)

                if grid is None:
                    # No motion — remove all sources
                    if self._current_grid is not None:
                        logger.info("All cameras idle — GPU sleeping")
                        self.pipeline.update_sources({})
                        self._current_grid = None
                else:
                    # Build active camera map
                    cameras = self.event_manager.get_camera_rtsp_urls()
                    active_sources = {
                        cam_id: cameras[cam_id]["rtsp_url"]
                        for cam_id in active_ids
                        if cam_id in cameras
                    }

                    # Handle rotation if needed
                    if grid.rotation_needed:
                        batches = self.grid_selector.get_rotation_batches(
                            list(active_sources.keys()), grid
                        )
                        # Process first batch (rotation handled by timer)
                        first_batch = {
                            cam_id: active_sources[cam_id]
                            for cam_id in batches[0]
                        }
                        self.pipeline.update_sources(first_batch)
                    else:
                        self.pipeline.update_sources(active_sources)

                    self._current_grid = grid

                # Flush expired trackers → create events
                finalized = self.best_shot.flush_expired()
                for event_data in finalized:
                    self.event_manager.process_detection(event_data)

                # Run scheduled jobs (nightly review)
                schedule.run_pending()

                time.sleep(self.POLL_INTERVAL)

            except Exception as e:
                logger.error(f"Orchestration error: {e}")
                time.sleep(5)

    def start(self):
        """Start the detector service."""
        logger.info("=" * 60)
        logger.info("Deep Vision by DNS — Detector Starting")
        logger.info(f"DeepStream available: {DEEPSTREAM_AVAILABLE}")
        logger.info(f"Motion threshold: {settings.motion_on_threshold}")
        logger.info(f"Off frames: {settings.motion_off_frames}")
        logger.info(f"Confidence threshold: {settings.confidence_threshold}")
        logger.info("=" * 60)

        self._running = True

        # Load cameras from DB
        self._load_cameras()

        # Build initial pipeline
        initial_grid = self.grid_selector.select(0)
        if initial_grid and DEEPSTREAM_AVAILABLE:
            self.pipeline.build_pipeline(initial_grid)
            self.pipeline.start()

        # Start motion gate
        self.motion_gate.start()

        # Schedule nightly review
        self.nightly.schedule_job()

        # Run orchestration loop
        self._orchestration_loop()

    def stop(self):
        """Gracefully stop all components."""
        logger.info("Detector shutting down...")
        self._running = False
        self.motion_gate.stop()
        self.pipeline.stop()
        logger.info("Detector stopped")


def main():
    service = DetectorService()

    # Handle graceful shutdown
    def signal_handler(sig, frame):
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    service.start()


if __name__ == "__main__":
    main()
