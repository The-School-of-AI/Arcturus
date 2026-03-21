"""
RAG blob storage — local filesystem or S3.

When RAG_S3_BUCKET is set, read/write use S3 with key = doc path.
Otherwise use PROJECT_ROOT/data/{doc}.
"""

import os
from pathlib import Path
from typing import Optional

PROJECT_ROOT = Path(__file__).parent.parent
DATA_ROOT = PROJECT_ROOT / "data"


def _normalize_doc(doc: str) -> str:
    """Normalize doc path: POSIX, no leading slash, no .."""
    return doc.strip("/").replace("\\", "/").replace("..", "").strip("/")


def _use_s3() -> bool:
    return bool(os.environ.get("RAG_S3_BUCKET", "").strip())


def read_doc(doc: str) -> Optional[bytes]:
    """Read document bytes. Returns None if not found."""
    key = _normalize_doc(doc)
    if not key:
        return None

    if _use_s3():
        try:
            import boto3
            bucket = os.environ.get("RAG_S3_BUCKET")
            prefix = os.environ.get("RAG_S3_PREFIX", "").strip().rstrip("/")
            full_key = f"{prefix}/{key}" if prefix else key
            endpoint = os.environ.get("RAG_S3_ENDPOINT_URL")
            kwargs = {}
            if endpoint:
                kwargs["endpoint_url"] = endpoint
            s3 = boto3.client("s3", **kwargs)
            obj = s3.get_object(Bucket=bucket, Key=full_key)
            return obj["Body"].read()
        except Exception as e:
            print(f"RAG S3 read error for {key}: {e}")
            return None

    path = DATA_ROOT / key
    if not path.exists() or not path.is_file():
        return None
    try:
        return path.read_bytes()
    except OSError:
        return None


def write_doc(doc: str, content: bytes) -> bool:
    """Write document bytes. Returns True on success."""
    key = _normalize_doc(doc)
    if not key:
        return False

    if _use_s3():
        try:
            import boto3
            bucket = os.environ.get("RAG_S3_BUCKET")
            prefix = os.environ.get("RAG_S3_PREFIX", "").strip().rstrip("/")
            full_key = f"{prefix}/{key}" if prefix else key
            endpoint = os.environ.get("RAG_S3_ENDPOINT_URL")
            kwargs = {}
            if endpoint:
                kwargs["endpoint_url"] = endpoint
            s3 = boto3.client("s3", **kwargs)
            s3.put_object(Bucket=bucket, Key=full_key, Body=content)
            return True
        except Exception as e:
            print(f"RAG S3 write error for {key}: {e}")
            return False

    path = DATA_ROOT / key
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        path.write_bytes(content)
        return True
    except OSError:
        return False


def exists_doc(doc: str) -> bool:
    """Check if document exists."""
    key = _normalize_doc(doc)
    if not key:
        return False

    if _use_s3():
        try:
            import boto3
            bucket = os.environ.get("RAG_S3_BUCKET")
            prefix = os.environ.get("RAG_S3_PREFIX", "").strip().rstrip("/")
            full_key = f"{prefix}/{key}" if prefix else key
            endpoint = os.environ.get("RAG_S3_ENDPOINT_URL")
            kwargs = {}
            if endpoint:
                kwargs["endpoint_url"] = endpoint
            s3 = boto3.client("s3", **kwargs)
            s3.head_object(Bucket=bucket, Key=full_key)
            return True
        except Exception:
            return False

    path = DATA_ROOT / key
    return path.exists() and path.is_file()
