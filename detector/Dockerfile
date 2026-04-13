FROM nvcr.io/nvidia/deepstream:7.1-triton-multiarch

ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VER=12
ENV PYTHONUNBUFFERED=1

# ── Python dependencies ──────────────────────────────────────
RUN pip3 install --no-cache-dir \
    ultralytics>=8.3.0 \
    psycopg2-binary>=2.9.0 \
    redis>=5.0 \
    minio>=7.0 \
    pydantic-settings>=2.0 \
    Pillow>=10.0 \
    numpy>=1.26.0 \
    schedule>=1.2.0

# ── DeepStream-Yolo: custom YOLO bbox parser ─────────────────
RUN git clone --depth 1 https://github.com/marcoslucianops/DeepStream-Yolo.git /opt/DeepStream-Yolo && \
    cd /opt/DeepStream-Yolo && \
    CUDA_VER=${CUDA_VER} make -C nvdsinfer_custom_impl_Yolo

# ── Export YOLOv8m to DeepStream-compatible ONNX ─────────────
RUN mkdir -p /opt/models && \
    cd /opt/DeepStream-Yolo && \
    python3 utils/export_yoloV8.py -w yolov8m.pt --dynamic && \
    mv yolov8m.onnx /opt/models/yolov8m.onnx && \
    cp labels.txt /opt/models/labels.txt

WORKDIR /app
COPY . .

CMD ["python3", "main.py"]
