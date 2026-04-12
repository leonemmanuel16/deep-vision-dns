"""Health monitoring endpoints."""

import os
import psutil
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from services.auth import get_current_user

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
def health_check():
    """Public health check endpoint."""
    return {"status": "ok", "service": "deep-vision-api"}


@router.get("/system")
def system_health(user=Depends(get_current_user)):
    """Detailed system health (requires auth)."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    gpu_info = _get_gpu_info()

    return {
        "cpu": {
            "percent": cpu_percent,
            "cores": psutil.cpu_count(),
        },
        "memory": {
            "total_gb": round(memory.total / (1024**3), 1),
            "used_gb": round(memory.used / (1024**3), 1),
            "percent": memory.percent,
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "percent": round(disk.percent, 1),
        },
        "gpu": gpu_info,
    }


@router.get("/db")
def db_health(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Database health check."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {"status": "ok", "connected": True}
    except Exception as e:
        return {"status": "error", "connected": False, "error": str(e)}


def _get_gpu_info() -> dict:
    """Get NVIDIA GPU info via nvidia-smi."""
    try:
        import subprocess
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,temperature.gpu,utilization.gpu,memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            return {
                "name": parts[0],
                "temperature_c": int(parts[1]),
                "utilization_percent": int(parts[2]),
                "memory_used_mb": int(parts[3]),
                "memory_total_mb": int(parts[4]),
            }
    except Exception:
        pass
    return {"available": False}
