"""Private S3-compatible object storage helpers for Minecraft release files."""

import os
import re
from pathlib import PurePosixPath

import boto3
from botocore.config import Config
from botocore.exceptions import BotoCoreError, ClientError


ALLOWED_CONTENT_TYPES = {
    ".jar": "application/java-archive",
    ".zip": "application/zip",
    ".mrpack": "application/x-modrinth-modpack",
}
PRESIGN_SECONDS = 15 * 60


class StorageUnavailable(RuntimeError):
    """Raised when R2 credentials are missing or the storage service cannot sign a URL."""


def content_type_for(filename: str) -> str:
    return ALLOWED_CONTENT_TYPES.get(PurePosixPath(filename).suffix.lower(), "application/octet-stream")


def storage_key(author_id: int, resource_id: int, filename: str) -> str:
    safe_name = re.sub(r"[^a-zA-Z0-9._-]+", "-", PurePosixPath(filename).name).strip("-.")
    return f"resources/{author_id}/{resource_id}/{safe_name or 'release.bin'}"


def _client():
    required = {
        "R2_ACCOUNT_ID": os.getenv("R2_ACCOUNT_ID"),
        "R2_ACCESS_KEY_ID": os.getenv("R2_ACCESS_KEY_ID"),
        "R2_SECRET_ACCESS_KEY": os.getenv("R2_SECRET_ACCESS_KEY"),
        "R2_BUCKET": os.getenv("R2_BUCKET"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise StorageUnavailable("Cloudflare R2 is not configured.")
    return (
        boto3.client(
            "s3",
            endpoint_url=f"https://{required['R2_ACCOUNT_ID']}.r2.cloudflarestorage.com",
            aws_access_key_id=required["R2_ACCESS_KEY_ID"],
            aws_secret_access_key=required["R2_SECRET_ACCESS_KEY"],
            region_name="auto",
            config=Config(signature_version="s3v4"),
        ),
        required["R2_BUCKET"],
    )


def create_upload_url(key: str, filename: str) -> tuple[str, str]:
    try:
        client, bucket = _client()
        content_type = content_type_for(filename)
        url = client.generate_presigned_url(
            "put_object",
            Params={"Bucket": bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=PRESIGN_SECONDS,
            HttpMethod="PUT",
        )
        return url, content_type
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable("Cloudflare R2 could not issue an upload URL.") from exc


def uploaded_size(key: str) -> int:
    try:
        client, bucket = _client()
        return int(client.head_object(Bucket=bucket, Key=key)["ContentLength"])
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable("The uploaded release file could not be verified.") from exc


def create_download_url(key: str, filename: str) -> str:
    try:
        client, bucket = _client()
        return client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": bucket,
                "Key": key,
                "ResponseContentDisposition": f'attachment; filename="{PurePosixPath(filename).name}"',
            },
            ExpiresIn=PRESIGN_SECONDS,
            HttpMethod="GET",
        )
    except (BotoCoreError, ClientError) as exc:
        raise StorageUnavailable("Cloudflare R2 could not issue a download URL.") from exc
