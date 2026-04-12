FROM nvcr.io/nvidia/deepstream:7.1-triton-multiarch

ENV DEBIAN_FRONTEND=noninteractive
ENV PYTHONUNBUFFERED=1

# Install Python dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3-pip python3-dev libglib2.0-0 libgl1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip3 install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py"]
