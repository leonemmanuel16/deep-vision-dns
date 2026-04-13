"""
Deep Vision by DNS — DeepStream + YOLOv8m Detector Service

Architecture:
  Motion Gate (CPU)  ->  filters active cameras
  DeepStream (GPU)   ->  nvstreammux -> nvinfer (YOLOv8m TRT) -> nvtracker (NvDCF)
  Probe              ->  extracts metadata + frames from GPU pipeline
  BestShotSelector   ->  picks best snapshot per tracker_id
  EventManager       ->  validates + stores events in PostgreSQL / MinIO / Redis

Fallback: if DeepStream/pyds is not available, uses Ultralytics YOLO + OpenCV.
"""

import io
import json
import signal
import logging
import time
import threading
import uuid
from datetime import datetime, timezone
from typing import Optional

import cv2
import numpy as np
import psycopg2
import psycopg2.extras
import redis
from minio import Minio
from minio.error import S3Error

from config import settings
from movement_filter import MovementFilter
from face_analyzer import FaceAnalyzer, FaceResult

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("detector")

# ── Check if DeepStream is available ─────────────────────────
import sys
# Add DeepStream lib paths for pyds
for _ds_path in [
    "/opt/nvidia/deepstream/deepstream/lib",
    "/opt/nvidia/deepstream/deepstream-7.1/lib",
]:
    if _ds_path not in sys.path:
        sys.path.insert(0, _ds_path)

try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib
    import pyds
    DEEPSTREAM_AVAILABLE = True
    Gst.init(None)
    logger.info("DeepStream + pyds loaded successfully")
except (ImportError, ValueError) as e:
    DEEPSTREAM_AVAILABLE = False
    logger.warning(f"DeepStream not available ({e}) — using YOLO fallback mode")


# ═══════════════════════════════════════════════════════════════
# LABELS
# ═══════════════════════════════════════════════════════════════

PERSON_LABELS = {"person"}
VEHICLE_LABELS = {"car", "truck", "bus", "motorcycle", "bicycle"}
ANIMAL_LABELS = {"cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe"}
EVENT_LABELS = PERSON_LABELS | VEHICLE_LABELS | ANIMAL_LABELS

YOLO_LABELS = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train",
    "truck", "boat", "traffic light", "fire hydrant", "stop sign",
    "parking meter", "bench", "bird", "cat", "dog", "horse", "sheep",
    "cow", "elephant", "bear", "zebra", "giraffe", "backpack", "umbrella",
    "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
    "sports ball", "kite", "baseball bat", "baseball glove", "skateboard",
    "surfboard", "tennis racket", "bottle", "wine glass", "cup", "fork",
    "knife", "spoon", "bowl", "banana", "apple", "sandwich", "orange",
    "broccoli", "carrot", "hot dog", "pizza", "donut", "cake", "chair",
    "couch", "potted plant", "bed", "dining table", "toilet", "tv",
    "laptop", "mouse", "remote", "keyboard", "cell phone", "microwave",
    "oven", "toaster", "sink", "refrigerator", "book", "clock", "vase",
    "scissors", "teddy bear", "hair drier", "toothbrush",
]


def classify_event_type(label: str) -> Optional[str]:
    if label in PERSON_LABELS:
        return "person_detected"
    elif label in VEHICLE_LABELS:
        return "vehicle_detected"
    elif label in ANIMAL_LABELS:
        return "animal_detected"
    return None


# ═══════════════════════════════════════════════════════════════
# DATABASE MANAGER
# ═══════════════════════════════════════════════════════════════

class DatabaseManager:
    """Thread-safe PostgreSQL manager."""

    def __init__(self):
        self._local = threading.local()

    def _get_conn(self):
        conn = getattr(self._local, "conn", None)
        if conn is None or conn.closed:
            conn = psycopg2.connect(settings.db_url)
            conn.autocommit = True
            self._local.conn = conn
        return conn

    def fetch_cameras(self) -> dict:
        conn = self._get_conn()
        cameras = {}
        try:
            with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, name, rtsp_url, rtsp_sub_url FROM cameras WHERE enabled = true"
                )
                for row in cur.fetchall():
                    cameras[str(row["id"])] = {
                        "name": row["name"],
                        "rtsp_url": row["rtsp_url"],
                        "rtsp_sub_url": row.get("rtsp_sub_url") or row["rtsp_url"],
                    }
        except Exception as e:
            logger.error(f"Failed to fetch cameras: {e}")
            self._local.conn = None
        return cameras

    def update_camera_status(self, camera_id: str, status: str):
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE cameras SET status = %s, updated_at = NOW() WHERE id = %s",
                    (status, camera_id),
                )
        except Exception as e:
            logger.error(f"Failed to update camera status: {e}")
            self._local.conn = None

    def insert_event(self, camera_id, event_type, label, confidence, bbox,
                     tracker_id, snapshot_url, detected_at,
                     person_id=None, face_data=None) -> Optional[str]:
        conn = self._get_conn()
        try:
            # Build attributes from face data
            attributes = {}
            if face_data and face_data.face_detected:
                attributes["face_detected"] = True
                attributes["face_confidence"] = face_data.face_confidence
                if face_data.person_name:
                    attributes["face_match"] = face_data.person_name
                    attributes["match_distance"] = face_data.match_distance
                if face_data.age:
                    attributes["edad_estimada"] = face_data.age
                if face_data.gender:
                    attributes["genero_estimado"] = face_data.gender
                if face_data.emotion:
                    attributes["emocion"] = face_data.emotion

            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO events (
                        camera_id, event_type, label, confidence,
                        bbox, tracker_id, snapshot_url,
                        review_pass, needs_deep_review, detected_at,
                        person_id, attributes
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,'online',true,%s,%s,%s)
                    RETURNING id""",
                    (camera_id, event_type, label, confidence,
                     json.dumps(bbox), tracker_id, snapshot_url, detected_at,
                     person_id, json.dumps(attributes) if attributes else '{}'),
                )
                result = cur.fetchone()
                return str(result[0]) if result else None
        except Exception as e:
            logger.error(f"Failed to insert event: {e}")
            self._local.conn = None
            return None


# ═══════════════════════════════════════════════════════════════
# SNAPSHOT UPLOADER
# ═══════════════════════════════════════════════════════════════

class SnapshotUploader:
    def __init__(self):
        self.client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_user,
            secret_key=settings.minio_password,
            secure=False,
        )
        self._ensure_bucket()

    def _ensure_bucket(self):
        bucket = settings.minio_bucket_snapshots
        try:
            if not self.client.bucket_exists(bucket):
                self.client.make_bucket(bucket)
                logger.info(f"Created MinIO bucket: {bucket}")
        except S3Error as e:
            logger.error(f"MinIO bucket check failed: {e}")

    def upload(self, frame: np.ndarray, camera_id: str, label: str) -> str:
        bucket = settings.minio_bucket_snapshots
        now = datetime.now(timezone.utc)
        date_prefix = now.strftime("%Y/%m/%d")
        filename = (
            f"{camera_id}/{date_prefix}/"
            f"{now.strftime('%H%M%S')}_{label}_{uuid.uuid4().hex[:8]}.jpg"
        )
        try:
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
            data = io.BytesIO(buf.tobytes())
            size = data.getbuffer().nbytes
            self.client.put_object(bucket, filename, data, length=size,
                                   content_type="image/jpeg")
            return f"{bucket}/{filename}"
        except Exception as e:
            logger.error(f"Snapshot upload failed: {e}")
            return ""


# ═══════════════════════════════════════════════════════════════
# DEEPSTREAM PIPELINE MODE
# ═══════════════════════════════════════════════════════════════

class SnapshotGrabber:
    """Lightweight RTSP frame grabber for snapshot capture.
    Maintains one OpenCV capture per camera, grabs frames on demand."""

    def __init__(self, cameras: dict):
        self._cameras = cameras
        self._captures: dict[str, cv2.VideoCapture] = {}
        self._lock = threading.Lock()
        self._last_frames: dict[str, tuple[np.ndarray, float]] = {}

    def grab_frame(self, camera_id: str) -> Optional[np.ndarray]:
        """Grab a frame from the camera's RTSP stream. Thread-safe."""
        # Return cached frame if less than 2 seconds old
        with self._lock:
            cached = self._last_frames.get(camera_id)
            if cached and (time.time() - cached[1]) < 2.0:
                return cached[0]

        cam_data = self._cameras.get(camera_id)
        if not cam_data:
            return None

        rtsp_url = cam_data.get("rtsp_sub_url") or cam_data["rtsp_url"]

        with self._lock:
            cap = self._captures.get(camera_id)
            if cap is None or not cap.isOpened():
                cap = cv2.VideoCapture(rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    return None
                self._captures[camera_id] = cap

            ret, frame = cap.read()
            if not ret:
                cap.release()
                self._captures.pop(camera_id, None)
                return None

            self._last_frames[camera_id] = (frame, time.time())
            return frame

    def stop(self):
        with self._lock:
            for cap in self._captures.values():
                cap.release()
            self._captures.clear()


class DeepStreamDetector:
    """Full DeepStream pipeline: decode (GPU) -> nvinfer (YOLO26m TRT) -> nvtracker."""

    def __init__(self, cameras: dict, db: DatabaseManager,
                 redis_client: redis.Redis, uploader: SnapshotUploader,
                 movement_filter: MovementFilter = None,
                 face_analyzer: FaceAnalyzer = None):
        self.cameras = cameras
        self.cam_id_list = list(cameras.keys())
        self.db = db
        self.redis_client = redis_client
        self.uploader = uploader
        self.movement_filter = movement_filter or MovementFilter()
        self.face_analyzer = face_analyzer or FaceAnalyzer()
        self.snapshot_grabber = SnapshotGrabber(cameras)

        self.pipeline = None
        self.loop = None
        self._thread = None

        # Dedup + stats + face tracking
        self._recent_trackers: dict[str, float] = {}
        self._face_analysis_count: dict[str, int] = {}  # tracker_key -> count
        self._lock = threading.Lock()
        self._stats = {"detections": 0, "events": 0, "frames": 0, "filtered_stationary": 0}

    def build_and_start(self):
        """Build GStreamer pipeline and start it."""
        num_sources = len(self.cameras)
        logger.info(f"Building DeepStream pipeline for {num_sources} cameras")

        self.pipeline = Gst.Pipeline.new("deepvision-pipeline")

        # ── nvstreammux ──
        streammux = Gst.ElementFactory.make("nvstreammux", "muxer")
        streammux.set_property("batch-size", num_sources)
        streammux.set_property("width", 1920)
        streammux.set_property("height", 1080)
        streammux.set_property("batched-push-timeout", 40000)
        streammux.set_property("live-source", 1)
        streammux.set_property("enable-padding", True)
        self.pipeline.add(streammux)

        # ── Add RTSP sources ──
        for i, (cam_id, cam_data) in enumerate(self.cameras.items()):
            rtsp_url = cam_data["rtsp_url"]
            source_bin = self._create_source_bin(i, rtsp_url)
            self.pipeline.add(source_bin)

            srcpad = source_bin.get_static_pad("src")
            sinkpad = streammux.request_pad_simple(f"sink_{i}")
            if srcpad and sinkpad:
                srcpad.link(sinkpad)
            logger.info(f"Source {i}: {cam_data['name']} -> {rtsp_url}")

        # ── nvinfer (YOLOv8m TensorRT) ──
        pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
        pgie.set_property("config-file-path", settings.pgie_config_path)
        pgie.set_property("batch-size", num_sources)
        self.pipeline.add(pgie)

        # ── nvtracker (NvDCF) ──
        tracker = Gst.ElementFactory.make("nvtracker", "tracker")
        tracker.set_property("tracker-width", 640)
        tracker.set_property("tracker-height", 480)
        tracker.set_property(
            "ll-lib-file",
            "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so",
        )
        tracker.set_property("ll-config-file", settings.tracker_config_path)
        try:
            tracker.set_property("enable-batch-process", True)
        except TypeError:
            pass  # Property not available in this DS version
        self.pipeline.add(tracker)

        # ── fakesink ──
        sink = Gst.ElementFactory.make("fakesink", "fakesink")
        sink.set_property("sync", 0)
        sink.set_property("async", False)
        self.pipeline.add(sink)

        # ── Link ──
        streammux.link(pgie)
        pgie.link(tracker)
        tracker.link(sink)

        # ── Attach probe on tracker src pad (metadata only, no frame extraction) ──
        tracker_src_pad = tracker.get_static_pad("src")
        tracker_src_pad.add_probe(Gst.PadProbeType.BUFFER, self._buffer_probe, 0)

        # ── Bus ──
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        # ── Start ──
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            logger.error("Failed to start DeepStream pipeline!")
            return False

        self.loop = GLib.MainLoop()
        self._thread = threading.Thread(target=self.loop.run, daemon=True)
        self._thread.start()

        logger.info("DeepStream pipeline PLAYING")
        return True

    def _create_source_bin(self, index: int, rtsp_url: str):
        """Create a source bin for RTSP decoding on GPU."""
        bin_name = f"source-bin-{index:02d}"
        nbin = Gst.Bin.new(bin_name)

        uri_decode = Gst.ElementFactory.make("uridecodebin", f"uri-decode-{index}")
        uri_decode.set_property("uri", rtsp_url)
        uri_decode.connect("pad-added", self._decodebin_pad_added, nbin)
        uri_decode.connect("child-added", self._decodebin_child_added, index)

        nbin.add(uri_decode)

        ghost_pad = Gst.GhostPad.new_no_target("src", Gst.PadDirection.SRC)
        nbin.add_pad(ghost_pad)

        return nbin

    @staticmethod
    def _decodebin_pad_added(dbin, pad, nbin):
        caps = pad.get_current_caps()
        if not caps:
            return
        struct = caps.get_structure(0)
        if struct.get_name().startswith("video"):
            ghost_pad = nbin.get_static_pad("src")
            if ghost_pad and not ghost_pad.is_linked():
                ghost_pad.set_target(pad)

    @staticmethod
    def _decodebin_child_added(child_proxy, obj, name, index):
        if "source" in name:
            obj.set_property("latency", 200)

    def _buffer_probe(self, pad, info, u_data):
        """Main probe: extract detections + frames, save events."""
        try:
            gst_buffer = info.get_buffer()
            if not gst_buffer:
                return Gst.PadProbeReturn.OK

            batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
            if batch_meta is None:
                return Gst.PadProbeReturn.OK
            l_frame = batch_meta.frame_meta_list
        except Exception as e:
            logger.error(f"Probe init error: {e}")
            return Gst.PadProbeReturn.OK

        while l_frame is not None:
            try:
                try:
                    frame_meta = pyds.NvDsFrameMeta.cast(l_frame.data)
                except StopIteration:
                    break

                source_id = frame_meta.source_id
                camera_id = (
                    self.cam_id_list[source_id]
                    if source_id < len(self.cam_id_list)
                    else f"unknown-{source_id}"
                )
                camera_name = self.cameras.get(camera_id, {}).get("name", f"Cam-{source_id}")
                self._stats["frames"] += 1

                # Frame extraction disabled — probe attached to tracker pad
                # (no nvvideoconvert/RGBA conversion). Snapshots captured via
                # OpenCV RTSP grab in a separate thread when events fire.
                frame = None

                l_obj = frame_meta.obj_meta_list
                now = time.time()

                while l_obj is not None:
                    try:
                        obj_meta = pyds.NvDsObjectMeta.cast(l_obj.data)
                    except StopIteration:
                        break

                    class_id = obj_meta.class_id
                    label = YOLO_LABELS[class_id] if class_id < len(YOLO_LABELS) else f"class_{class_id}"
                    confidence = obj_meta.confidence
                    tracker_id = obj_meta.object_id

                    event_type = classify_event_type(label)
                    if event_type is None:
                        try:
                            l_obj = l_obj.next
                        except StopIteration:
                            break
                        continue

                    # Bounding box
                    rect = obj_meta.rect_params
                    bbox = {
                        "x1": round(rect.left, 1),
                        "y1": round(rect.top, 1),
                        "x2": round(rect.left + rect.width, 1),
                        "y2": round(rect.top + rect.height, 1),
                    }

                    self._stats["detections"] += 1

                    # Movement filter: track position and check if moving
                    self.movement_filter.update_position(
                        camera_id, int(tracker_id), bbox, label
                    )
                    if not self.movement_filter.should_alert(
                        camera_id, int(tracker_id), label
                    ):
                        self._stats["filtered_stationary"] += 1
                        try:
                            l_obj = l_obj.next
                        except StopIteration:
                            break
                        continue

                    # Dedup by tracker_id
                    dedup_key = f"t:{camera_id}:{tracker_id}"
                    with self._lock:
                        last_seen = self._recent_trackers.get(dedup_key)
                        if last_seen and (now - last_seen) < settings.dedup_window_seconds:
                            try:
                                l_obj = l_obj.next
                            except StopIteration:
                                break
                            continue
                        self._recent_trackers[dedup_key] = now

                    # Upload snapshot (grab via RTSP)
                    snapshot_url = ""
                    if frame is None:
                        frame = self.snapshot_grabber.grab_frame(camera_id)
                    if frame is not None:
                        snapshot_url = self.uploader.upload(frame, camera_id, label)

                    # Face analysis for person detections
                    face_result = FaceResult()
                    person_id = None
                    if label == "person" and frame is not None and self.face_analyzer.enabled:
                        face_key = f"fa:{camera_id}:{tracker_id}"
                        with self._lock:
                            self._face_analysis_count.setdefault(face_key, 0)
                            self._face_analysis_count[face_key] += 1
                            should_analyze = (
                                self._face_analysis_count[face_key] %
                                settings.face_analyze_every_n == 1
                            )
                        if should_analyze:
                            face_result = self.face_analyzer.analyze(frame, bbox, camera_id=camera_id)
                            if face_result.person_id:
                                person_id = face_result.person_id

                    # Publish to Redis
                    payload_data = {
                        "camera_id": camera_id,
                        "camera_name": camera_name,
                        "label": label,
                        "event_type": event_type,
                        "confidence": round(confidence, 3),
                        "bbox": bbox,
                        "tracker_id": int(tracker_id),
                        "timestamp": now,
                    }
                    if face_result.face_detected:
                        payload_data["face"] = {
                            "detected": True,
                            "confidence": face_result.face_confidence,
                            "person_id": face_result.person_id,
                            "person_name": face_result.person_name,
                            "is_unknown": face_result.is_unknown,
                            "age": face_result.age,
                            "gender": face_result.gender,
                            "emotion": face_result.emotion,
                        }
                    try:
                        self.redis_client.publish(f"detections:{camera_id}", json.dumps(payload_data))
                        self.redis_client.publish("detections:all", json.dumps(payload_data))
                    except Exception:
                        pass

                    # Save event to DB
                    detected_at = datetime.now(timezone.utc)
                    event_id = self.db.insert_event(
                        camera_id=camera_id,
                        event_type=event_type,
                        label=label,
                        confidence=confidence,
                        bbox=bbox,
                        tracker_id=int(tracker_id),
                        snapshot_url=snapshot_url,
                        detected_at=detected_at,
                        person_id=person_id,
                        face_data=face_result if face_result.face_detected else None,
                    )

                    if event_id:
                        self._stats["events"] += 1
                        face_info = ""
                        if face_result.face_detected:
                            if face_result.person_name:
                                face_info = f" face={face_result.person_name}"
                            else:
                                face_info = " face=unknown"
                        logger.info(
                            f"[{camera_name}] {event_type} label={label} "
                            f"conf={confidence:.2f} tracker={tracker_id}{face_info} id={event_id}"
                        )

                    try:
                        l_obj = l_obj.next
                    except StopIteration:
                        break

                # Clean old dedup entries periodically
                if self._stats["frames"] % 500 == 0:
                    self._clean_dedup(now)

            except Exception as e:
                logger.error(f"Buffer probe frame error: {e}", exc_info=True)

            try:
                l_frame = l_frame.next
            except StopIteration:
                break

        return Gst.PadProbeReturn.OK

    def _clean_dedup(self, now: float):
        cutoff = now - settings.dedup_window_seconds * 2
        with self._lock:
            self._recent_trackers = {
                k: v for k, v in self._recent_trackers.items() if v > cutoff
            }

    def _on_bus_message(self, bus, message):
        t = message.type
        if t == Gst.MessageType.EOS:
            logger.info("Pipeline EOS")
            if self.loop:
                self.loop.quit()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err.message} | {debug}")
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Pipeline warning: {err.message}")

    def stop(self):
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        if self.loop:
            self.loop.quit()
        self.snapshot_grabber.stop()
        logger.info("DeepStream pipeline stopped")

    def get_stats(self) -> dict:
        return dict(self._stats)


# ═══════════════════════════════════════════════════════════════
# FALLBACK: YOLO + OpenCV (when DeepStream is not available)
# ═══════════════════════════════════════════════════════════════

class YOLOFallbackProcessor:
    """OpenCV RTSP + Ultralytics YOLO fallback for non-DeepStream environments."""

    def __init__(self, camera_id, camera_name, rtsp_url,
                 db, redis_client, uploader,
                 movement_filter: MovementFilter = None,
                 face_analyzer: FaceAnalyzer = None):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.db = db
        self.redis_client = redis_client
        self.uploader = uploader
        self.movement_filter = movement_filter or MovementFilter()
        self.face_analyzer = face_analyzer or FaceAnalyzer()
        self._stop = threading.Event()
        self._thread = None
        self._recent_trackers: dict[str, float] = {}
        self._face_analysis_count: dict[str, int] = {}
        self._stats = {"frames": 0, "detections": 0, "events": 0, "filtered_stationary": 0}

    def start(self):
        self._thread = threading.Thread(target=self._run, daemon=True,
                                         name=f"yolo-{self.camera_name}")
        self._thread.start()

    def stop(self):
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=10)

    def _run(self):
        from yolo_detector import YOLODetector
        detector = YOLODetector()

        while not self._stop.is_set():
            cap = None
            try:
                logger.info(f"[{self.camera_name}] Connecting RTSP: {self.rtsp_url}")
                cap = cv2.VideoCapture(self.rtsp_url, cv2.CAP_FFMPEG)
                cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                if not cap.isOpened():
                    raise ConnectionError("Failed to open RTSP")
                logger.info(f"[{self.camera_name}] Connected")
                self.db.update_camera_status(self.camera_id, "online")

                fails = 0
                while not self._stop.is_set():
                    ret, frame = cap.read()
                    if not ret:
                        fails += 1
                        if fails > 30:
                            raise ConnectionError("Lost stream")
                        time.sleep(0.05)
                        continue
                    fails = 0
                    self._stats["frames"] += 1

                    if self._stats["frames"] % settings.process_every_n_frames != 0:
                        continue

                    detections = detector.detect(frame, use_tracker=True)
                    if not detections:
                        continue

                    now = time.time()
                    for det in detections:
                        self._stats["detections"] += 1

                        # Movement filter: track position and check if moving
                        tid = det.tracker_id or 0
                        self.movement_filter.update_position(
                            self.camera_id, tid, det.bbox, det.label
                        )
                        if not self.movement_filter.should_alert(
                            self.camera_id, tid, det.label
                        ):
                            self._stats["filtered_stationary"] += 1
                            continue

                        dedup_key = (
                            f"t:{det.tracker_id}" if det.tracker_id
                            else f"g:{det.label}:{int((det.bbox['x1']+det.bbox['x2'])/400)}"
                        )
                        last = self._recent_trackers.get(dedup_key)
                        if last and (now - last) < settings.dedup_window_seconds:
                            continue
                        self._recent_trackers[dedup_key] = now

                        snapshot_url = self.uploader.upload(frame, self.camera_id, det.label)

                        # Face analysis for person detections
                        face_result = FaceResult()
                        person_id = None
                        if det.label == "person" and self.face_analyzer.enabled:
                            face_key = f"fa:{self.camera_id}:{tid}"
                            self._face_analysis_count.setdefault(face_key, 0)
                            self._face_analysis_count[face_key] += 1
                            if self._face_analysis_count[face_key] % settings.face_analyze_every_n == 1:
                                face_result = self.face_analyzer.analyze(frame, det.bbox, camera_id=self.camera_id)
                                if face_result.person_id:
                                    person_id = face_result.person_id

                        event_id = self.db.insert_event(
                            camera_id=self.camera_id, event_type=det.event_type,
                            label=det.label, confidence=det.confidence,
                            bbox=det.bbox, tracker_id=det.tracker_id,
                            snapshot_url=snapshot_url,
                            detected_at=datetime.now(timezone.utc),
                            person_id=person_id,
                            face_data=face_result if face_result.face_detected else None,
                        )
                        if event_id:
                            self._stats["events"] += 1
                            face_info = ""
                            if face_result.face_detected:
                                face_info = f" face={'matched:' + face_result.person_name if face_result.person_name else 'unknown'}"
                            logger.info(
                                f"[{self.camera_name}] {det.event_type} "
                                f"label={det.label} conf={det.confidence:.2f}{face_info}"
                            )

                    if self._stats["frames"] % 300 == 0:
                        cutoff = now - settings.dedup_window_seconds * 2
                        self._recent_trackers = {
                            k: v for k, v in self._recent_trackers.items() if v > cutoff
                        }

            except Exception as e:
                logger.error(f"[{self.camera_name}] Error: {e}")
                self.db.update_camera_status(self.camera_id, "offline")
            finally:
                if cap:
                    cap.release()

            if not self._stop.is_set():
                logger.info(f"[{self.camera_name}] Reconnecting in {settings.reconnect_interval}s")
                self._stop.wait(timeout=settings.reconnect_interval)


# ═══════════════════════════════════════════════════════════════
# MAIN SERVICE
# ═══════════════════════════════════════════════════════════════

class DetectorService:
    """Orchestrates DeepStream or YOLO fallback detector."""

    def __init__(self):
        self._running = False
        self.db = DatabaseManager()
        self.uploader = SnapshotUploader()
        self.movement_filter = MovementFilter()
        self.face_analyzer = FaceAnalyzer(snapshot_uploader=self.uploader)
        self.redis_client = None
        self._ds_detector = None
        self._fallback_processors = []

    def start(self):
        logger.info("=" * 60)
        logger.info("Deep Vision by DNS — Detector Service")
        logger.info(f"DeepStream available: {DEEPSTREAM_AVAILABLE}")
        logger.info(f"Model: {settings.yolo_model} (YOLO26 NMS-free)")
        logger.info(f"Confidence threshold: {settings.confidence_threshold}")
        logger.info(f"Dedup window: {settings.dedup_window_seconds}s")
        logger.info(f"Movement filter: {'ON' if settings.movement_filter_enabled else 'OFF'}")
        if settings.movement_filter_enabled:
            logger.info(f"  Min displacement: {settings.movement_min_displacement}px")
            logger.info(f"  Required for: {settings.movement_required_labels}")
        logger.info(f"Face recognition: {'ON' if settings.face_recognition_enabled else 'OFF'}")
        if settings.face_recognition_enabled:
            logger.info(f"  Model: {settings.face_recognition_model} + {settings.face_detector_backend}")
            logger.info(f"  Match threshold: {settings.face_match_threshold}")
        logger.info("=" * 60)

        # Redis
        self.redis_client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
        try:
            self.redis_client.ping()
            logger.info("Redis connected")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

        # Load cameras
        cameras = self.db.fetch_cameras()
        if not cameras:
            logger.warning("No enabled cameras found — waiting...")
            while not cameras:
                time.sleep(10)
                cameras = self.db.fetch_cameras()

        logger.info(f"Loaded {len(cameras)} cameras")

        # Update all cameras to online
        for cam_id in cameras:
            self.db.update_camera_status(cam_id, "online")

        self._running = True

        if DEEPSTREAM_AVAILABLE:
            self._start_deepstream(cameras)
        else:
            self._start_yolo_fallback(cameras)

        # Stats loop (main thread)
        self._stats_loop()

    def _start_deepstream(self, cameras: dict):
        """Start DeepStream GPU pipeline."""
        self._ds_detector = DeepStreamDetector(
            cameras=cameras,
            db=self.db,
            redis_client=self.redis_client,
            uploader=self.uploader,
            movement_filter=self.movement_filter,
            face_analyzer=self.face_analyzer,
        )
        success = self._ds_detector.build_and_start()
        if not success:
            logger.error("DeepStream failed to start — falling back to YOLO")
            self._start_yolo_fallback(cameras)

    def _start_yolo_fallback(self, cameras: dict):
        """Start YOLO + OpenCV threads (one per camera)."""
        logger.info("Starting YOLO fallback mode")
        for cam_id, cam_data in cameras.items():
            proc = YOLOFallbackProcessor(
                camera_id=cam_id,
                camera_name=cam_data["name"],
                rtsp_url=cam_data["rtsp_url"],
                db=self.db,
                redis_client=self.redis_client,
                uploader=self.uploader,
                movement_filter=self.movement_filter,
                face_analyzer=self.face_analyzer,
            )
            self._fallback_processors.append(proc)
            proc.start()
            logger.info(f"Started YOLO processor: {cam_data['name']}")

    def _stats_loop(self):
        """Log stats every N seconds on the main thread."""
        while self._running:
            time.sleep(settings.stats_interval_seconds)
            if not self._running:
                break

            # Movement filter stats
            mf_stats = self.movement_filter.get_stats()

            if self._ds_detector:
                stats = self._ds_detector.get_stats()
                logger.info(
                    f"Stats [DeepStream] frames={stats['frames']} "
                    f"detections={stats['detections']} events={stats['events']} "
                    f"filtered_stationary={stats.get('filtered_stationary', 0)}"
                )
            else:
                total_det = sum(p._stats["detections"] for p in self._fallback_processors)
                total_evt = sum(p._stats["events"] for p in self._fallback_processors)
                total_filtered = sum(p._stats.get("filtered_stationary", 0) for p in self._fallback_processors)
                for p in self._fallback_processors:
                    s = p._stats
                    logger.info(
                        f"Stats [{p.camera_name}] frames={s['frames']} "
                        f"det={s['detections']} events={s['events']} "
                        f"filtered={s.get('filtered_stationary', 0)}"
                    )
                logger.info(
                    f"Stats [TOTAL] cameras={len(self._fallback_processors)} "
                    f"detections={total_det} events={total_evt} "
                    f"filtered_stationary={total_filtered}"
                )

            logger.info(
                f"Stats [MovementFilter] tracked={mf_stats['tracked_objects']} "
                f"moving={mf_stats['moving']} stationary={mf_stats['stationary']}"
            )

            if self.face_analyzer.enabled:
                face_stats = self.face_analyzer.get_stats()
                logger.info(
                    f"Stats [FaceAnalyzer] analyzed={face_stats['faces_analyzed']} "
                    f"detected={face_stats['faces_detected']} "
                    f"matched={face_stats['faces_matched']} "
                    f"unknown={face_stats['faces_unknown']} "
                    f"known_persons={face_stats['known_persons']}"
                )

    def stop(self):
        logger.info("Detector shutting down...")
        self._running = False
        if self._ds_detector:
            self._ds_detector.stop()
        for proc in self._fallback_processors:
            proc.stop()
        logger.info("Detector stopped")


def main():
    service = DetectorService()

    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down...")
        service.stop()

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    service.start()


if __name__ == "__main__":
    main()
