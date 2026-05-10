"""GovGuard™ — S3 File Storage"""
import io
from typing import Optional
import aioboto3
from fastapi import UploadFile
from core.config import settings


def _get_session():
    return aioboto3.Session(region_name=settings.AWS_REGION)


async def upload_evidence(tenant_id: str, grant_id: str, file: UploadFile) -> str:
    """Upload evidence file to S3; return object key."""
    import uuid
    key = f"evidence/{tenant_id}/{grant_id}/{uuid.uuid4()}/{file.filename}"
    session = _get_session()
    async with session.client("s3") as s3:
        await s3.upload_fileobj(
            file.file,
            settings.S3_EVIDENCE_BUCKET,
            key,
            ExtraArgs={
                "ServerSideEncryption": "aws:kms",
                **({"SSEKMSKeyId": settings.KMS_KEY_ID} if settings.KMS_KEY_ID else {}),
                "ContentType": file.content_type or "application/octet-stream",
            },
        )
    return key


async def get_presigned_url(bucket: str, key: str, expires: int = 900) -> str:
    """Generate a pre-signed GET URL valid for `expires` seconds."""
    session = _get_session()
    async with session.client("s3") as s3:
        url = await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": key},
            ExpiresIn=expires,
        )
    return url


async def upload_bytes(bucket: str, key: str, data: bytes, content_type: str = "application/octet-stream") -> None:
    session = _get_session()
    async with session.client("s3") as s3:
        await s3.upload_fileobj(
            io.BytesIO(data),
            bucket,
            key,
            ExtraArgs={"ServerSideEncryption": "aws:kms", "ContentType": content_type},
        )
