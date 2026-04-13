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

# ── Logging ──────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s","level":"%(levelname)s","module":"%(name)s","msg":"%(message)s"}',
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger("detector")

# ── Check if DeepStream is available ─────────────────────────
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
                     tracker_id, snapshot_url, detected_at) -> Optional[str]:
        conn = self._get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """INSERT INTO events (
                        camera_id, event_type, label, confidence,
                        bbox, tracker_id, snapshot_url,
                        review_pass, needs_deep_review, detected_at
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,'online',true,%s)
                    RETURNING id""",
                    (camera_id, event_type, label, confidence,
                     json.dumps(bbox), tracker_id, snapshot_url, detected_at),
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

class DeepStreamDetector:
    """Full DeepStream pipeline: decode (GPU) -> nvinfer (YOLOv8m TRT) -> nvtracker."""

    def __init__(self, cameras: dict, db: DatabaseManager,
                 redis_client: redis.Redis, uploader: SnapshotUploader):
        self.cameras = cameras
        self.cam_id_list = list(cameras.keys())
        self.db = db
        self.redis_client = redis_client
        self.uploader = uploader

        self.pipeline = None
        self.loop = None
        self._thread = None

        # Dedup + stats
        self._recent_trackers: dict[str, float] = {}
        self._lock = threading.Lock()
        self._stats = {"detections": 0, "events": 0, "frames": 0}

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
        tracker.set_property("enable-batch-process", True)
        self.pipeline.add(tracker)

        # ── nvvideoconvert (for frame extraction in probe) ──
        nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
        self.pipeline.add(nvvidconv)

        capsfilter = Gst.ElementFactory.make("capsfilter", "capsfilter")
        caps = Gst.Caps.from_string("video/x-raw(memory:NVMM), format=RGBA")
        capsfilter.set_property("caps", caps)
        self.pipeline.add(capsfilter)

        # ── fakesink ──
        sink = Gst.ElementFactory.make("fakesink", "fakesink")
        sink.set_property("sync", 0)
        sink.set_property("async", False)
        self.pipeline.add(sink)

        # ── Link ──
        streammux.link(pgie)
        pgie.link(tracker)
        tracker.link(nvvidconv)
        nvvidconv.link(capsfilter)
        capsfilter.link(sink)

        # ── Attach probe after capsfilter ──
        sink_pad = capsfilter.get_static_pad("src")
        sink_pad.add_probe(Gst.PadProbeType.BUFFER, self._buffer_probe, 0)

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
        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        l_frame = batch_meta.frame_meta_list

        while l_frame is not None:
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

            # Extract frame for snapshots (RGBA -> BGR)
            frame = None
            try:
                n_frame = pyds.get_nvds_buf_surface(hash(gst_buffer), frame_meta.batch_id)
                frame = np.array(n_frame, copy=True, order="C")
                frame = cv2.cvtColor(frame, cv2.COLOR_RGBA2BGR)
            except Exception:
                pass

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

                # Upload snapshot
                snapshot_url = ""
                if frame is not None:
                    snapshot_url = self.uploader.upload(frame, camera_id, label)

                # Publish to Redis
                payload = json.dumps({
                    "camera_id": camera_id,
                    "camera_name": camera_name,
                    "label": label,
                    "event_type": event_type,
                    "confidence": round(confidence, 3),
                    "bbox": bbox,
                    "tracker_id": int(tracker_id),
                    "timestamp": now,
                })
                try:
                    self.redis_client.publish(f"detections:{camera_id}", payload)
                    self.redis_client.publish("detections:all", payload)
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
                )

                if event_id:
                    self._stats["events"] += 1
                    logger.info(
                        f"[{camera_name}] {event_type} label={label} "
                        f"conf={confidence:.2f} tracker={tracker_id} id={event_id}"
                    )

                try:
                    l_obj = l_obj.next
                except StopIteration:
                    break

            # Clean old dedup entries periodically
            if self._stats["frames"] % 500 == 0:
                self._clean_dedup(now)

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
        logger.info("DeepStream pipeline stopped")

    def get_stats(self) -> dict:
        return dict(self._stats)


# ═══════════════════════════════════════════════════════════════
# FALLBACK: YOLO + OpenCV (when DeepStream is not available)
# ═══════════════════════════════════════════════════════════════

class YOLOFallbackProcessor:
    """OpenCV RTSP + Ultralytics YOLO fallback for non-DeepStream environments."""

    def __init__(self, camera_id, camera_name, rtsp_url,
                 db, redis_client, uploader):
        self.camera_id = camera_id
        self.camera_name = camera_name
        self.rtsp_url = rtsp_url
        self.db = db
        self.redis_client = redis_client
        self.uploader = uploader
        self._stop = threading.Event()
        self._thread = None
        self._recent_trackers: dict[str, float] = {}
        self._stats = {"frames": 0, "detections": 0, "events": 0}

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
                        dedup_key = (
                            f"t:{det.tracker_id}" if det.tracker_id
                            else f"g:{det.label}:{int((det.bbox['x1']+det.bbox['x2'])/400)}"
                        )
                        last = self._recent_trackers.get(dedup_key)
                        if last and (now - last) < settings.dedup_window_seconds:
                            continue
                        self._recent_trackers[dedup_key] = now

                        snapshot_url = self.uploader.upload(frame, self.camera_id, det.label)
                        event_id = self.db.insert_event(
                            camera_id=self.camera_id, event_type=det.event_type,
                            label=det.label, confidence=det.confidence,
                            bbox=det.bbox, tracker_id=det.tracker_id,
                            snapshot_url=snapshot_url,
                            detected_at=datetime.now(timezone.utc),
                        )
                        if event_id:
                            self._stats["events"] += 1
                            logger.info(
                                f"[{self.camera_name}] {det.event_type} "
                                f"label={det.label} conf={det.confidence:.2f}"
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

            if self._ds_detector:
                stats = self._ds_detector.get_stats()
                logger.info(
                    f"Stats [DeepStream] frames={stats['frames']} "
                    f"detections={stats['detections']} events={stats['events']}"
                )
            else:
                total_det = sum(p._stats["detections"] for p in self._fallback_processors)
                total_evt = sum(p._stats["events"] for p in self._fallback_processors)
                for p in self._fallback_processors:
                    s = p._stats
                    logger.info(
                        f"Stats [{p.camera_name}] frames={s['frames']} "
                        f"det={s['detections']} events={s['events']}"
                    )
                logger.info(
                    f"Stats [TOTAL] cameras={len(self._fallback_processors)} "
                    f"detections={total_det} events={total_evt}"
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
