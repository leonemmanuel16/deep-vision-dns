#!/bin/bash
# Deep Vision Detector — Entrypoint
# Copies ONNX model files to persistent volume if not already present.
# The TensorRT engine (built on first run) persists in the volume.

set -e

echo "=== Deep Vision Detector Entrypoint ==="

# Ensure /opt/models directory exists (it's the Docker volume mount point)
mkdir -p /opt/models

# Copy ONNX model if not present in the volume
if [ ! -f /opt/models/yolo26m.onnx ]; then
    echo "Copying ONNX model to persistent volume..."
    cp /opt/models-base/yolo26m.onnx /opt/models/yolo26m.onnx
    echo "  -> yolo26m.onnx copied"
else
    echo "ONNX model already in volume: /opt/models/yolo26m.onnx"
fi

# Copy external weights if they exist
if [ -f /opt/models-base/yolo26m.onnx.data ] && [ ! -f /opt/models/yolo26m.onnx.data ]; then
    cp /opt/models-base/yolo26m.onnx.data /opt/models/yolo26m.onnx.data
    echo "  -> yolo26m.onnx.data copied"
fi

# Copy labels
if [ ! -f /opt/models/labels.txt ]; then
    cp /opt/models-base/labels.txt /opt/models/labels.txt
    echo "  -> labels.txt copied"
fi

# Check if TensorRT engine already exists (from previous run)
if ls /opt/models/*.engine 1>/dev/null 2>&1; then
    echo "TensorRT engine found! Skipping rebuild."
    ls -lh /opt/models/*.engine
else
    echo "No TensorRT engine found. Will be built on first run (~5-10 min on T1000)."
fi

echo "=== Starting detector ==="

# Execute the CMD
exec "$@"
