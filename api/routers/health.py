"""Health monitoring endpoints."""

import os
import time
import psutil
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import get_db
from services.auth import get_current_user

router = APIRouter(prefix="/health", tags=["health"])

_boot_time = psutil.boot_time()


@router.get("/")
def health_check():
    """Public health check endpoint."""
    return {"status": "ok", "service": "deep-vision-api"}


@router.get("/system")
def system_health(user=Depends(get_current_user)):
    """Detailed system health with per-core CPU, swap, GPU details."""
    # CPU
    cpu_percent = psutil.cpu_percent(interval=0.3)
    cpu_per_core = psutil.cpu_percent(percpu=True)
    cpu_count_physical = psutil.cpu_count(logical=False) or psutil.cpu_count()
    cpu_count_logical = psutil.cpu_count()
    cpu_freq = psutil.cpu_freq()
    load_avg = os.getloadavg() if hasattr(os, "getloadavg") else [0, 0, 0]

    # Memory
    memory = psutil.virtual_memory()
    swap = psutil.swap_memory()

    # Disk
    disk = psutil.disk_usage("/")

    # Uptime
    uptime_seconds = int(time.time() - _boot_time)
    days = uptime_seconds // 86400
    hours = (uptime_seconds % 86400) // 3600
    minutes = (uptime_seconds % 3600) // 60
    uptime_str = f"{days}d {hours}h {minutes}m"

    # GPU
    gpu_info = _get_gpu_info()

    return {
        "cpu": {
            "percent": cpu_percent,
            "per_core": cpu_per_core,
            "cores_physical": cpu_count_physical,
            "cores_logical": cpu_count_logical,
            "freq_mhz": round(cpu_freq.current) if cpu_freq else 0,
            "load_avg": [round(x, 2) for x in load_avg],
        },
        "memory": {
            "total_gb": round(memory.total / (1024**3), 1),
            "used_gb": round(memory.used / (1024**3), 1),
            "available_gb": round(memory.available / (1024**3), 1),
            "percent": memory.percent,
        },
        "swap": {
            "total_gb": round(swap.total / (1024**3), 1),
            "used_gb": round(swap.used / (1024**3), 1),
            "percent": round(swap.percent, 1),
        },
        "disk": {
            "total_gb": round(disk.total / (1024**3), 1),
            "used_gb": round(disk.used / (1024**3), 1),
            "free_gb": round(disk.free / (1024**3), 1),
            "percent": round(disk.percent, 1),
            "mount": "/",
            "device": _get_disk_device(),
        },
        "gpu": gpu_info,
        "uptime": {
            "seconds": uptime_seconds,
            "formatted": uptime_str,
        },
    }


@router.get("/db")
def db_health(db: Session = Depends(get_db), user=Depends(get_current_user)):
    """Database health check."""
    try:
        result = db.execute(text("SELECT 1")).scalar()
        return {"status": "ok", "connected": True}
    except Exception as e:
        return {"status": "error", "connected": False, "error": str(e)}


def _get_disk_device() -> str:
    """Get root disk device name."""
    try:
        for p in psutil.disk_partitions():
            if p.mountpoint == "/":
                return p.device
    except Exception:
        pass
    return "/dev/sda"


def _get_gpu_info() -> dict:
    """Get NVIDIA GPU info via nvidia-smi."""
    try:
        import subprocess
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,temperature.gpu,utilization.gpu,"
                "memory.used,memory.total,fan.speed,power.draw,power.limit",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            parts = [p.strip() for p in result.stdout.strip().split(", ")]
            return {
                "available": True,
                "name": parts[0],
                "temperature_c": int(parts[1]) if parts[1] not in ("[N/A]", "") else 0,
                "utilization_percent": int(parts[2]) if parts[2] not in ("[N/A]", "") else 0,
                "memory_used_mb": int(parts[3]) if parts[3] not in ("[N/A]", "") else 0,
                "memory_total_mb": int(parts[4]) if parts[4] not in ("[N/A]", "") else 0,
                "fan_percent": int(parts[5]) if len(parts) > 5 and parts[5] not in ("[N/A]", "") else 0,
                "power_draw_w": round(float(parts[6]), 1) if len(parts) > 6 and parts[6] not in ("[N/A]", "") else 0,
                "power_limit_w": round(float(parts[7]), 1) if len(parts) > 7 and parts[7] not in ("[N/A]", "") else 0,
            }
    except Exception:
        pass
    return {"available": False}
