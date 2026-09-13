import boto3
from botocore.client import Config
from config.settings import settings


def get_storage_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.storage_endpoint_url,
        aws_access_key_id=settings.storage_access_key,
        aws_secret_access_key=settings.storage_secret_key,
        config=Config(signature_version="s3v4"),
        region_name="us-east-1",
    )


def upload_bytes(key: str, data: bytes, content_type: str = "image/png") -> str:
    client = get_storage_client()
    client.put_object(
        Bucket=settings.storage_bucket,
        Key=key,
        Body=data,
        ContentType=content_type,
    )
    return f"{settings.storage_public_url}/{key}"


def ensure_bucket_exists():
    client = get_storage_client()
    try:
        client.head_bucket(Bucket=settings.storage_bucket)
    except Exception:
        client.create_bucket(Bucket=settings.storage_bucket)
