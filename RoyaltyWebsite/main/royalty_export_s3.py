"""S3 helpers for per-user royalty CSV exports (metadata in DB, bytes in S3)."""
from __future__ import annotations

import io
from typing import Optional

import boto3
from botocore.exceptions import ClientError
from django.conf import settings


def _client():
    return boto3.client(
        "s3",
        region_name=getattr(settings, "AWS_S3_REGION_NAME", None) or "us-west-1",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def royalty_export_bucket() -> Optional[str]:
    return getattr(settings, "AWS_STORAGE_BUCKET_NAME", None) or None


def upload_royalty_export_csv(s3_key: str, body: bytes, content_type: str = "text/csv") -> None:
    bucket = royalty_export_bucket()
    if not bucket:
        raise RuntimeError("AWS_STORAGE_BUCKET_NAME is not configured.")
    _client().upload_fileobj(
        io.BytesIO(body),
        bucket,
        s3_key,
        ExtraArgs={"ContentType": content_type},
    )


def delete_royalty_export_object(s3_key: str) -> bool:
    bucket = royalty_export_bucket()
    if not bucket:
        return False
    try:
        _client().delete_object(Bucket=bucket, Key=s3_key)
        return True
    except ClientError:
        return False


def presigned_get_url(s3_key: str, expire_seconds: int, filename: str) -> str:
    bucket = royalty_export_bucket()
    if not bucket:
        raise RuntimeError("AWS_STORAGE_BUCKET_NAME is not configured.")
    return _client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket": bucket,
            "Key": s3_key,
            "ResponseContentDisposition": f'attachment; filename="{filename}"',
        },
        ExpiresIn=expire_seconds,
    )
