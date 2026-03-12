"""
Servicio de almacenamiento — soporta Google Cloud Storage (GCP) y AWS S3.
Selección automática según STORAGE_BACKEND en .env ("gcs" | "s3").
Por defecto: GCS (recomendado para despliegue en Google Cloud).
"""
import uuid
import hashlib
from typing import Optional
import structlog

from app.core.config import settings

logger = structlog.get_logger()


# ─── Selector de backend ─────────────────────────────────────────────────────

def _use_gcs() -> bool:
    return settings.STORAGE_BACKEND.lower() == "gcs"


# ─── Google Cloud Storage ────────────────────────────────────────────────────

def _get_gcs_client():
    try:
        from google.cloud import storage as gcs
        import os
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = settings.GOOGLE_APPLICATION_CREDENTIALS
        return gcs.Client(project=settings.GCS_PROJECT_ID or None)
    except ImportError:
        raise RuntimeError(
            "google-cloud-storage no instalado.\n"
            "Ejecuta: pip install google-cloud-storage"
        )


async def _gcs_upload(content: bytes, gcs_key: str, mime_type: str, bucket_name: str) -> dict:
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_key)
    blob.upload_from_string(content, content_type=mime_type)
    # Cifrado: GCS usa AES-256 por defecto (GMEK) en todos los buckets
    checksum = hashlib.sha256(content).hexdigest()
    blob.metadata = {"checksum-sha256": checksum, "uploaded-by": "pathos-system"}
    blob.patch()
    logger.info("gcs_upload_success", bucket=bucket_name, key=gcs_key, size=len(content))
    return {"bucket": bucket_name, "key": gcs_key, "size": len(content), "checksum": checksum}


def _gcs_presigned_url(gcs_key: str, expires_seconds: int, bucket_name: str) -> str:
    import datetime
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_key)
    url = blob.generate_signed_url(
        expiration=datetime.timedelta(seconds=expires_seconds),
        method="GET",
        version="v4",
    )
    logger.info("gcs_presigned_url_generated", key=gcs_key, expires=expires_seconds)
    return url


async def _gcs_delete(gcs_key: str, bucket_name: str) -> bool:
    try:
        client = _get_gcs_client()
        bucket = client.bucket(bucket_name)
        blob = bucket.blob(gcs_key)
        blob.delete()
        logger.info("gcs_delete_success", bucket=bucket_name, key=gcs_key)
        return True
    except Exception as e:
        logger.error("gcs_delete_failed", key=gcs_key, error=str(e))
        return False


async def _gcs_download(gcs_key: str, bucket_name: str) -> bytes:
    client = _get_gcs_client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(gcs_key)
    return blob.download_as_bytes()


# ─── AWS S3 ──────────────────────────────────────────────────────────────────

def _get_s3_client():
    try:
        import boto3
        return boto3.client(
            "s3",
            region_name=settings.AWS_REGION,
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        )
    except ImportError:
        raise RuntimeError("boto3 no instalado. Ejecuta: pip install boto3")


async def _s3_upload(content: bytes, s3_key: str, mime_type: str, bucket_name: str) -> dict:
    s3 = _get_s3_client()
    checksum = hashlib.sha256(content).hexdigest()
    s3.put_object(
        Bucket=bucket_name, Key=s3_key, Body=content,
        ContentType=mime_type, ServerSideEncryption="AES256",
        Metadata={"checksum-sha256": checksum, "uploaded-by": "pathos-system"},
    )
    logger.info("s3_upload_success", bucket=bucket_name, key=s3_key, size=len(content))
    return {"bucket": bucket_name, "key": s3_key, "size": len(content), "checksum": checksum}


def _s3_presigned_url(s3_key: str, expires_seconds: int, bucket_name: str) -> str:
    s3 = _get_s3_client()
    return s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket_name, "Key": s3_key},
        ExpiresIn=expires_seconds,
    )


async def _s3_delete(s3_key: str, bucket_name: str) -> bool:
    try:
        s3 = _get_s3_client()
        s3.delete_object(Bucket=bucket_name, Key=s3_key)
        return True
    except Exception as e:
        logger.error("s3_delete_failed", key=s3_key, error=str(e))
        return False


async def _s3_download(s3_key: str, bucket_name: str) -> bytes:
    s3 = _get_s3_client()
    return s3.get_object(Bucket=bucket_name, Key=s3_key)["Body"].read()


# ─── API pública (agnóstica al backend) ──────────────────────────────────────

def build_storage_key(document_type: str, patient_id: str, case_id: str, filename: str) -> str:
    """Genera la ruta del objeto en GCS/S3."""
    safe = filename.replace(" ", "_").replace("/", "-")
    uid = str(uuid.uuid4())[:8]
    return f"{document_type}/{patient_id}/{case_id}/{uid}_{safe}"


def _resolve_bucket(bucket: Optional[str]) -> str:
    if bucket:
        return bucket
    return settings.GCS_BUCKET_NAME if _use_gcs() else settings.S3_BUCKET_NAME


async def upload_document(
    content: bytes,
    storage_key: str,
    mime_type: str = "application/pdf",
    bucket: Optional[str] = None,
) -> dict:
    """Sube un documento cifrado. Usa GCS o S3 según STORAGE_BACKEND."""
    target = _resolve_bucket(bucket)
    if _use_gcs():
        return await _gcs_upload(content, storage_key, mime_type, target)
    return await _s3_upload(content, storage_key, mime_type, target)


def generate_presigned_url(
    storage_key: str,
    expires_seconds: int = 300,
    bucket: Optional[str] = None,
) -> str:
    """URL de descarga temporal (5 min por defecto)."""
    target = _resolve_bucket(bucket)
    if _use_gcs():
        return _gcs_presigned_url(storage_key, expires_seconds, target)
    return _s3_presigned_url(storage_key, expires_seconds, target)


async def delete_document(storage_key: str, bucket: Optional[str] = None) -> bool:
    target = _resolve_bucket(bucket)
    if _use_gcs():
        return await _gcs_delete(storage_key, target)
    return await _s3_delete(storage_key, target)


async def get_document_content(storage_key: str, bucket: Optional[str] = None) -> bytes:
    target = _resolve_bucket(bucket)
    if _use_gcs():
        return await _gcs_download(storage_key, target)
    return await _s3_download(storage_key, target)


# Alias de compatibilidad con código anterior
build_s3_key = build_storage_key
