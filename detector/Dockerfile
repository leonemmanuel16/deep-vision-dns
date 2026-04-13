FROM nvcr.io/nvidia/deepstream:7.1-triton-multiarch

ENV DEBIAN_FRONTEND=noninteractive
ENV CUDA_VER=12
ENV PYTHONUNBUFFERED=1

# ── Install pyds (DeepStream Python bindings) ────────────────
# Note: import test skipped because libcuda.so.1 is only available at runtime
RUN pip3 install --no-cache-dir \
    https://github.com/NVIDIA-AI-IOT/deepstream_python_apps/releases/download/v1.2.0/pyds-1.2.0-cp310-cp310-linux_x86_64.whl

# ── Python dependencies ──────────────────────────────────────
# Force-remove distutils-installed blinker that blocks pip upgrades
RUN pip3 install --no-cache-dir --ignore-installed blinker && \
    pip3 install --no-cache-dir \
    ultralytics>=8.3.0 \
    psycopg2-binary>=2.9.0 \
    redis>=5.0 \
    minio>=7.0 \
    pydantic-settings>=2.0 \
    Pillow>=10.0 \
    numpy>=1.26.0 \
    schedule>=1.2.0 \
    onnx>=1.16.0 \
    onnxslim \
    onnxruntime \
    onnxscript \
    deepface>=0.0.93 \
    tf-keras

# ── DeepStream-Yolo: custom YOLO bbox parser ─────────────────
RUN git clone --depth 1 https://github.com/marcoslucianops/DeepStream-Yolo.git /opt/DeepStream-Yolo && \
    cd /opt/DeepStream-Yolo && \
    CUDA_VER=${CUDA_VER} make -C nvdsinfer_custom_impl_Yolo

# ── Download YOLO26m and export to DeepStream-compatible ONNX ─
# Models saved to /opt/models-base (baked into image)
# At runtime, entrypoint copies to /opt/models (persistent volume)
RUN mkdir -p /opt/models-base && \
    python3 -c "from ultralytics import YOLO; YOLO('yolo26m.pt')" && \
    cp yolo26m.pt /opt/DeepStream-Yolo/ && \
    cd /opt/DeepStream-Yolo && \
    python3 utils/export_yolo26.py -w yolo26m.pt --dynamic && \
    mv yolo26m.onnx /opt/models-base/yolo26m.onnx && \
    if [ -f yolo26m.onnx.data ]; then mv yolo26m.onnx.data /opt/models-base/yolo26m.onnx.data; fi && \
    cp labels.txt /opt/models-base/labels.txt

WORKDIR /app
COPY . .

# Entrypoint: copy ONNX models to volume if not present, then run detector
RUN chmod +x /app/entrypoint.sh 2>/dev/null || true
ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["python3", "main.py"]
