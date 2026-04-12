"""Snapshot proxy — serves images stored in MinIO."""

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from minio import Minio
from minio.error import S3Error

from config import settings
from services.auth import get_current_user

router = APIRouter(prefix="/snapshots", tags=["snapshots"])

_client: Minio | None = None


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
    """Return a snapshot image from MinIO.

    The *path* matches the ``snapshot_url`` stored in the events table, e.g.
    ``snapshots/ea0b3fdb-.../2026/04/12/235315_car_2dceb168.jpg``.

    If the path starts with the bucket name we strip it so the MinIO lookup
    uses only the object key.
    """
    bucket = settings.minio_bucket_snapshots
    object_name = path

    # Strip leading bucket name if present (e.g. "snapshots/…" -> "…")
    if object_name.startswith(f"{bucket}/"):
        object_name = object_name[len(bucket) + 1 :]

    client = _get_minio()
    try:
        response = client.get_object(bucket, object_name)
        data = response.read()
        response.close()
        response.release_conn()
    except S3Error as exc:
        if exc.code == "NoSuchKey":
            raise HTTPException(status_code=404, detail="Snapshot not found")
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
