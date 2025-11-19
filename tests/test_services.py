import os
import sys
import base64
from types import SimpleNamespace
from pathlib import Path

# Ensure project root is on sys.path so `apps` package can be imported during collection
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Ensure env for services import during test collection
os.environ.setdefault('DATABASE_URL', f"sqlite://{os.path.join(os.getcwd(), 'test_db.sqlite3')}")
os.environ.setdefault('STORAGE_BACKEND', 'local')
os.environ.setdefault('LOCAL_STORAGE_PATH', os.path.join(os.getcwd(), '.test_storage'))

import asyncio

from apps.uploader.services import decode_base64_data, LocalStorage, S3HTTPStorage


def test_decode_base64_accepts_data_uri():
    raw = b'hello world'
    b64 = base64.b64encode(raw).decode('ascii')
    data_uri = f'data:text/plain;base64,{b64}'
    decoded = decode_base64_data(data_uri)
    assert decoded == raw


def test_decode_base64_accepts_plain_base64():
    raw = b'abc123'
    b64 = base64.b64encode(raw).decode('ascii')
    decoded = decode_base64_data(b64)
    assert decoded == raw


def test_local_storage_roundtrip(tmp_path):
    storage = LocalStorage(str(tmp_path))
    data = b'bytes-data'
    asyncio.run(storage.put('file.bin', data))
    got = asyncio.run(storage.get('file.bin'))
    assert got == data


class DummyResponse:
    def __init__(self, status_code=200, content=b'', text=''):
        self.status_code = status_code
        self.content = content
        self.text = text


class DummyClient:
    # Shared store across instances so separate context managers see the same data
    _shared_store = {}

    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def put(self, url, content=None, headers=None):
        DummyClient._shared_store[url] = content
        return DummyResponse(status_code=200, content=b'', text='OK')

    async def get(self, url, headers=None):
        if url not in DummyClient._shared_store:
            return DummyResponse(status_code=404, content=b'', text='Not Found')
        return DummyResponse(status_code=200, content=DummyClient._shared_store[url], text='OK')


def test_s3_http_storage_put_get(monkeypatch):
    # Monkeypatch httpx.AsyncClient used in S3HTTPStorage
    import apps.uploader.services as svc

    monkeypatch.setattr('apps.uploader.services.httpx.AsyncClient', DummyClient)

    s3 = S3HTTPStorage(endpoint='https://example.com', bucket='b', access_key='a', secret_key='s')
    data = b'hello-s3'
    asyncio.run(s3.put('obj1', data))
    got = asyncio.run(s3.get('obj1'))
    assert got == data
