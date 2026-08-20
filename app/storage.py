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
        "B2_S3_ENDPOINT": os.getenv("B2_S3_ENDPOINT"),
        "B2_KEY_ID": os.getenv("B2_KEY_ID"),
        "B2_APPLICATION_KEY": os.getenv("B2_APPLICATION_KEY"),
        "B2_BUCKET": os.getenv("B2_BUCKET"),
        "B2_REGION": os.getenv("B2_REGION"),
    }
    missing = [name for name, value in required.items() if not value]
    if missing:
        raise StorageUnavailable("Backblaze B2 is not configured.")
    endpoint = required["B2_S3_ENDPOINT"].rstrip("/")
    if not endpoint.startswith("https://"):
        endpoint = f"https://{endpoint}"
    return (
        boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=required["B2_KEY_ID"],
            aws_secret_access_key=required["B2_APPLICATION_KEY"],
            region_name=required["B2_REGION"],
            config=Config(signature_version="s3v4"),
        ),
        required["B2_BUCKET"],
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
        raise StorageUnavailable("Backblaze B2 could not issue an upload URL.") from exc


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
        raise StorageUnavailable("Backblaze B2 could not issue a download URL.") from exc
