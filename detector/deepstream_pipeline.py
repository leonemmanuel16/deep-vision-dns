"""
DeepStream 7.1 Pipeline — GPU-accelerated video analytics.

Pipeline: nvstreammux → nvinfer (YOLO) → nvtracker → nvdsanalytics → probe
All decoding and inference happens on GPU (zero-copy).
"""

import logging
import threading
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# DeepStream/GStreamer imports — only available on NVIDIA runtime
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib
    import pyds
    DEEPSTREAM_AVAILABLE = True
except ImportError:
    DEEPSTREAM_AVAILABLE = False
    logger.warning("DeepStream/pyds not available — running in stub mode")

from config import settings
from grid_selector import GridConfig


# COCO class labels for YOLO
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


class DeepStreamPipeline:
    """
    Manages a DeepStream pipeline for GPU-accelerated inference.
    Dynamically adds/removes RTSP sources based on Motion Gate output.
    """

    def __init__(self, probe_callback: Optional[Callable] = None):
        self.probe_callback = probe_callback
        self.pipeline = None
        self.streammux = None
        self.loop = None
        self._thread: Optional[threading.Thread] = None
        self._source_bins: dict[str, object] = {}
        self._source_ids: dict[str, int] = {}
        self._next_source_id = 0

        if DEEPSTREAM_AVAILABLE:
            Gst.init(None)

    def build_pipeline(self, grid: GridConfig):
        """
        Build the DeepStream pipeline with the given grid configuration.
        """
        if not DEEPSTREAM_AVAILABLE:
            logger.warning("DeepStream not available, pipeline not built")
            return

        self.pipeline = Gst.Pipeline.new("deepvision-pipeline")

        # ── Stream Muxer ──
        self.streammux = Gst.ElementFactory.make("nvstreammux", "muxer")
        self.streammux.set_property("batch-size", grid.batch_size)
        self.streammux.set_property("width", grid.cell_width)
        self.streammux.set_property("height", grid.cell_height)
        self.streammux.set_property("batched-push-timeout", 40000)
        self.streammux.set_property("live-source", True)
        self.streammux.set_property("enable-padding", True)
        self.pipeline.add(self.streammux)

        # ── Primary Inference (YOLO TensorRT) ──
        pgie = Gst.ElementFactory.make("nvinfer", "primary-inference")
        pgie.set_property("config-file-path", "/app/configs/pgie_yolo_config.txt")
        pgie.set_property("batch-size", grid.batch_size)
        self.pipeline.add(pgie)

        # ── Tracker (NvDCF) ──
        tracker = Gst.ElementFactory.make("nvtracker", "tracker")
        tracker.set_property("tracker-width", 640)
        tracker.set_property("tracker-height", 480)
        tracker.set_property("ll-lib-file", "/opt/nvidia/deepstream/deepstream/lib/libnvds_nvmultiobjecttracker.so")
        tracker.set_property("ll-config-file", "/app/configs/tracker_config.yml")
        tracker.set_property("enable-batch-process", True)
        self.pipeline.add(tracker)

        # ── Analytics (Zones & Lines) ──
        analytics = Gst.ElementFactory.make("nvdsanalytics", "analytics")
        analytics.set_property("config-file", "/app/configs/analytics_config.txt")
        self.pipeline.add(analytics)

        # ── Video Convert + OSD ──
        nvvidconv = Gst.ElementFactory.make("nvvideoconvert", "convertor")
        self.pipeline.add(nvvidconv)

        nvosd = Gst.ElementFactory.make("nvdsosd", "osd")
        self.pipeline.add(nvosd)

        # ── Fake Sink (we extract data via probe, no display needed) ──
        sink = Gst.ElementFactory.make("fakesink", "sink")
        sink.set_property("sync", False)
        sink.set_property("async", False)
        self.pipeline.add(sink)

        # ── Link elements ──
        self.streammux.link(pgie)
        pgie.link(tracker)
        tracker.link(analytics)
        analytics.link(nvvidconv)
        nvvidconv.link(nvosd)
        nvosd.link(sink)

        # ── Attach probe to OSD sink pad ──
        if self.probe_callback:
            osd_sink_pad = nvosd.get_static_pad("sink")
            osd_sink_pad.add_probe(
                Gst.PadProbeType.BUFFER,
                self._probe_wrapper,
            )

        logger.info(f"DeepStream pipeline built: batch={grid.batch_size}, "
                     f"resolution={grid.cell_width}x{grid.cell_height}")

    def _probe_wrapper(self, pad, info):
        """GStreamer probe wrapper that calls the user-provided callback."""
        if not DEEPSTREAM_AVAILABLE:
            return Gst.PadProbeReturn.OK

        gst_buffer = info.get_buffer()
        if not gst_buffer:
            return Gst.PadProbeReturn.OK

        batch_meta = pyds.gst_buffer_get_nvds_batch_meta(hash(gst_buffer))
        if self.probe_callback:
            self.probe_callback(batch_meta, self._source_ids)

        return Gst.PadProbeReturn.OK

    def add_source(self, camera_id: str, rtsp_url: str):
        """Add an RTSP source to the running pipeline."""
        if not DEEPSTREAM_AVAILABLE or not self.pipeline:
            return

        source_id = self._next_source_id
        self._next_source_id += 1

        # Create uridecodebin for RTSP
        uri_decode_bin = Gst.ElementFactory.make("uridecodebin", f"source-{source_id}")
        uri_decode_bin.set_property("uri", rtsp_url)
        uri_decode_bin.connect("pad-added", self._on_pad_added, source_id)

        self.pipeline.add(uri_decode_bin)
        uri_decode_bin.sync_state_with_parent()

        self._source_bins[camera_id] = uri_decode_bin
        self._source_ids[camera_id] = source_id
        logger.info(f"Added source {camera_id} (id={source_id})")

    def remove_source(self, camera_id: str):
        """Remove an RTSP source from the pipeline."""
        if camera_id not in self._source_bins:
            return

        source_bin = self._source_bins.pop(camera_id)
        source_id = self._source_ids.pop(camera_id)

        source_bin.set_state(Gst.State.NULL)
        self.pipeline.remove(source_bin)

        # Release muxer sink pad
        pad_name = f"sink_{source_id}"
        mux_pad = self.streammux.get_static_pad(pad_name)
        if mux_pad:
            self.streammux.release_request_pad(mux_pad)

        logger.info(f"Removed source {camera_id} (id={source_id})")

    def _on_pad_added(self, src, new_pad, source_id: int):
        """Handle new pad from uridecodebin — link to streammux."""
        caps = new_pad.get_current_caps()
        if not caps:
            return

        struct = caps.get_structure(0)
        if not struct.get_name().startswith("video"):
            return

        pad_name = f"sink_{source_id}"
        sinkpad = self.streammux.request_pad_simple(pad_name)
        if sinkpad and not sinkpad.is_linked():
            new_pad.link(sinkpad)

    def start(self):
        """Start the pipeline in a background thread."""
        if not DEEPSTREAM_AVAILABLE:
            logger.warning("DeepStream not available, pipeline not started")
            return

        self.loop = GLib.MainLoop()
        bus = self.pipeline.get_bus()
        bus.add_signal_watch()
        bus.connect("message", self._on_bus_message)

        self.pipeline.set_state(Gst.State.PLAYING)

        self._thread = threading.Thread(target=self.loop.run, daemon=True)
        self._thread.start()
        logger.info("DeepStream pipeline started")

    def stop(self):
        """Stop the pipeline."""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
        if self.loop:
            self.loop.quit()
        logger.info("DeepStream pipeline stopped")

    def _on_bus_message(self, bus, message):
        """Handle GStreamer bus messages."""
        t = message.type
        if t == Gst.MessageType.EOS:
            logger.info("Pipeline reached EOS")
            self.stop()
        elif t == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"Pipeline error: {err.message} | {debug}")
        elif t == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"Pipeline warning: {err.message}")

    def update_sources(self, active_cameras: dict[str, str]):
        """
        Update pipeline sources to match active cameras.
        active_cameras: {camera_id: rtsp_url}
        """
        current = set(self._source_bins.keys())
        desired = set(active_cameras.keys())

        # Remove cameras that went idle
        for cam_id in current - desired:
            self.remove_source(cam_id)

        # Add cameras that became active
        for cam_id in desired - current:
            self.add_source(cam_id, active_cameras[cam_id])
