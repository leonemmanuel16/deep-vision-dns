FROM python:3.10-slim

ENV PYTHONUNBUFFERED=1
ENV TF_CPP_MIN_LOG_LEVEL=3
# Force TensorFlow to CPU — no GPU needed for face analysis
ENV CUDA_VISIBLE_DEVICES=""

# System dependencies for OpenCV
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip install --no-cache-dir \
    fastapi>=0.100.0 \
    uvicorn[standard]>=0.20.0 \
    python-multipart>=0.0.6 \
    pydantic-settings>=2.0 \
    psycopg2-binary>=2.9.0 \
    minio>=7.0 \
    numpy>=1.26.0 \
    opencv-python-headless>=4.8.0 \
    Pillow>=10.0 \
    deepface>=0.0.93 \
    tf-keras \
    tensorflow-cpu>=2.15.0

WORKDIR /app
COPY . .

EXPOSE 8002
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002"]
