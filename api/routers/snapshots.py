"""Snapshot proxy — serves images stored in MinIO."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from minio import Minio
from minio.error import S3Error

from config import settings
from services.auth import get_current_user

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

_client: Minio | None = None

# Buckets that are allowed to be served
ALLOWED_BUCKETS = {"snapshots", "persons", "clips"}


def _get_minio() -> Minio:
    global _client
    if _client is None:
        _client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_user,
            secret_key=settings.minio_password,
            secure=False,
        )
    return _client


@router.get("/{path:path}")
def get_snapshot(path: str, user=Depends(get_current_user)):
    """Return an image from MinIO.

    Supports multiple buckets. The *path* format is ``bucket/object_key``.
    If the first segment matches an allowed bucket, it's used as the bucket
    name. Otherwise, the default snapshots bucket is assumed.

    Examples:
      ``snapshots/ea0b3fdb-.../car.jpg``  -> bucket=snapshots, key=ea0b3fdb-.../car.jpg
      ``persons/a1b2c3d4.jpg``            -> bucket=persons, key=a1b2c3d4.jpg
      ``ea0b3fdb-.../car.jpg``            -> bucket=snapshots (default), key=ea0b3fdb-.../car.jpg
    """
    # Determine bucket and object key
    bucket = settings.minio_bucket_snapshots  # default
    object_name = path

    # Check if path starts with a known bucket name
    first_segment = path.split("/", 1)[0] if "/" in path else ""
    if first_segment in ALLOWED_BUCKETS:
        bucket = first_segment
        object_name = path[len(first_segment) + 1:]

    if not object_name:
        raise HTTPException(status_code=400, detail="No object path specified")

    client = _get_minio()

    # Ensure bucket exists
    try:
        if not client.bucket_exists(bucket):
            raise HTTPException(status_code=404, detail=f"Bucket '{bucket}' not found")
    except S3Error:
        pass

    try:
        response = client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="Image not found")
        raise HTTPException(status_code=502, detail=f"MinIO error: {exc.code}")
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc))

    # Determine media type from extension
    media_type = "image/jpeg"
    if path.lower().endswith(".png"):
        media_type = "image/png"

    return Response(
        content=data,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=86400"},
    )
