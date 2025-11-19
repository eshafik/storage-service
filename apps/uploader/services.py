import base64
import hashlib
import hmac
import os
import re
from typing import Optional, Protocol
from urllib.parse import urlparse
from datetime import datetime, timezone

import httpx
from tortoise.transactions import in_transaction

from config.settings import STORAGE_BACKEND, LOCAL_STORAGE_PATH, S3_BUCKET, S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, \
    S3_REGION
from apps.uploader.models import BlobMeta, BlobData


class StorageInterface(Protocol):
    async def put(self, blob_id: str, data: bytes) -> None:
        ...

    async def get(self, blob_id: str) -> Optional[bytes]:
        ...


class LocalStorage:
    def __init__(self, base_path: str):
        self.base_path = base_path
        os.makedirs(self.base_path, exist_ok=True)

    async def put(self, blob_id: str, data: bytes) -> None:
        path = os.path.join(self.base_path, blob_id)
        dirpath = os.path.dirname(path)
        if dirpath:
            os.makedirs(dirpath, exist_ok=True)
        with open(path, 'wb') as f:
            f.write(data)

    async def get(self, blob_id: str) -> Optional[bytes]:
        path = os.path.join(self.base_path, blob_id)
        if not os.path.exists(path):
            return None
        with open(path, 'rb') as f:
            return f.read()


class DBStorage:
    """Store binary data in a separate DB table (BlobData)."""

    async def put(self, blob_id: str, data: bytes) -> None:
        # upsert into BlobData
        async with in_transaction():
            existing = await BlobData.filter(id=blob_id).first()
            if existing:
                existing.data = data
                await existing.save()
            else:
                await BlobData.create(id=blob_id, data=data)

    async def get(self, blob_id: str) -> Optional[bytes]:
        row = await BlobData.filter(id=blob_id).first()
        if not row:
            return None
        return row.data


class S3HTTPStorage:

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str | None = None,
        virtual_host: bool = False,
    ):
        self.endpoint = endpoint.rstrip('/')
        self.bucket = bucket
        self.access_key = access_key
        self.secret_key = secret_key
        self.service = "s3"
        self.virtual_host = virtual_host

        parsed = urlparse(self.endpoint)
        self.host = parsed.netloc
        self.region = region or self._extract_region(self.endpoint)

    def _extract_region(self, endpoint: str) -> str:
        """Auto-detect region from endpoint URL"""
        patterns = [
            r's3[.-]([a-z0-9-]+)\.amazonaws\.com',
            r'([a-z0-9-]+)\.digitaloceanspaces\.com',
            r'([a-z0-9-]+)\.linodeobjects\.com',
            r's3\.([a-z0-9-]+)\.backblazeb2\.com',
            r's3\.([a-z0-9-]+)\.wasabisys\.com',
        ]
        for p in patterns:
            match = re.search(p, endpoint)
            if match:
                return match.group(1)

        # MinIO and generic S3 services commonly use "us-east-1"
        return "us-east-1"

    def _sign(self, key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode('utf-8'), hashlib.sha256).digest()

    def _get_signature_key(self, date_stamp: str) -> bytes:
        k_date = self._sign(f"AWS4{self.secret_key}".encode('utf-8'), date_stamp)
        k_region = self._sign(k_date, self.region)
        k_service = self._sign(k_region, self.service)
        return self._sign(k_service, 'aws4_request')

    def _make_url_and_path(self, blob_id: str):
        """
        Supports both:
            - path-style:       https://endpoint/bucket/blob
            - virtual-host:     https://bucket.endpoint/blob
        """
        if self.virtual_host:
            url = f"{self.endpoint.replace('//', f'//{self.bucket}.')}/{blob_id}"
            path = f"/{blob_id}"
        else:
            url = f"{self.endpoint}/{self.bucket}/{blob_id}"
            path = f"/{self.bucket}/{blob_id}"

        return url, path

    def _auth_headers(self, method: str, path: str, payload: bytes = b'') -> dict:
        if not self.access_key or not self.secret_key:
            return {}

        now = datetime.now(timezone.utc)
        amz_date = now.strftime('%Y%m%dT%H%M%SZ')
        date_stamp = now.strftime('%Y%m%d')

        payload_hash = hashlib.sha256(payload).hexdigest()

        canonical_headers = (
            f'host:{self.host}\n'
            f'x-amz-content-sha256:{payload_hash}\n'
            f'x-amz-date:{amz_date}\n'
        )

        signed_headers = "host;x-amz-content-sha256;x-amz-date"

        canonical_request = (
            f"{method}\n"
            f"{path}\n"
            f""  # no query string
            f"\n{canonical_headers}\n"
            f"{signed_headers}\n"
            f"{payload_hash}"
        )

        string_to_sign = (
            f"AWS4-HMAC-SHA256\n"
            f"{amz_date}\n"
            f"{date_stamp}/{self.region}/s3/aws4_request\n"
            f"{hashlib.sha256(canonical_request.encode()).hexdigest()}"
        )

        signature = hmac.new(
            self._get_signature_key(date_stamp),
            string_to_sign.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        auth = (
            f"AWS4-HMAC-SHA256 "
            f"Credential={self.access_key}/{date_stamp}/{self.region}/s3/aws4_request, "
            f"SignedHeaders={signed_headers}, "
            f"Signature={signature}"
        )

        return {
            "Authorization": auth,
            "x-amz-date": amz_date,
            "x-amz-content-sha256": payload_hash,
        }

    async def put(self, blob_id: str, data: bytes) -> None:
        url, path = self._make_url_and_path(blob_id)
        headers = self._auth_headers("PUT", path, data)
        headers["Content-Type"] = "application/octet-stream"

        async with httpx.AsyncClient() as client:
            resp = await client.put(url, content=data, headers=headers)
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"S3 PUT failed: {resp.status_code} {resp.text}")

    async def get(self, blob_id: str):
        url, path = self._make_url_and_path(blob_id)
        headers = self._auth_headers("GET", path, b"")

        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers)
            if resp.status_code == 200:
                return resp.content
            if resp.status_code == 404:
                return None
            raise RuntimeError(f"S3 GET failed: {resp.status_code} {resp.text}")


def pick_storage() -> StorageInterface:
    """Pick storage implementation based on environment variables.

    FALLBACK order: LOCAL -> DB -> S3
    """
    storage_type = STORAGE_BACKEND.lower()
    if storage_type == 'db':
        return DBStorage()
    if storage_type == 's3':
        endpoint = S3_ENDPOINT
        bucket = S3_BUCKET
        access = S3_ACCESS_KEY
        secret = S3_SECRET_KEY
        region = S3_REGION
        return S3HTTPStorage(endpoint=endpoint, bucket=bucket, region=region,
                             access_key=access, secret_key=secret, virtual_host=False)
    # default local
    base = LOCAL_STORAGE_PATH
    return LocalStorage(base)


async def save_blob(blob_id: str, data_b64: str) -> None:
    try:
        data = base64.b64decode(data_b64)
    except Exception as e:
        raise ValueError('Invalid base64 data') from e

    storage = pick_storage()
    await storage.put(blob_id, data)

    # create metadata
    size = len(data)
    backend = STORAGE_BACKEND
    await BlobMeta.create(id=blob_id, size=size, backend=backend)


async def get_blob(blob_id: str) -> Optional[dict]:
    meta = await BlobMeta.filter(id=blob_id).first()
    if not meta:
        return None
    storage = pick_storage()
    data = await storage.get(blob_id)
    if data is None:
        return None
    data_b64 = base64.b64encode(data).decode('ascii')
    return {
        'id': meta.id,
        'data': data_b64,
        'size': meta.size,
        'created_at': meta.created_at.isoformat()
    }
