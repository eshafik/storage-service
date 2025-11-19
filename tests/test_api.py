import os
import sys
import base64
import tempfile
from types import SimpleNamespace
from pathlib import Path

# Ensure project root is importable during pytest collection
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Ensure environment vars are present before importing app/services (pytest may import modules during collection)
os.environ.setdefault('DATABASE_URL', f"sqlite://{os.path.join(os.getcwd(), 'test_db.sqlite3')}")
os.environ.setdefault('STORAGE_BACKEND', 'local')
os.environ.setdefault('LOCAL_STORAGE_PATH', os.path.join(os.getcwd(), '.test_storage'))

from fastapi.testclient import TestClient

import apps.uploader.services as svc
from main import app
from utils.jwt import generate_jwt_token


def test_api_create_and_get_blob(tmp_path, monkeypatch):
    # configure uploader to use local storage in tmp_path
    svc.STORAGE_BACKEND = 'local'
    svc.LOCAL_STORAGE_PATH = str(tmp_path)

    # initialize Tortoise DB so middleware connections check passes
    from config.db import init_db, close_db
    import asyncio

    asyncio.run(init_db())
    # ensure no leftover metadata for the test id
    from apps.uploader.models import BlobMeta

    async def _cleanup():
        obj = await BlobMeta.filter(id='obj1').first()
        if obj:
            await obj.delete()

    asyncio.run(_cleanup())
    client = TestClient(app)

    # create a fake user-like object for token generation
    user = SimpleNamespace(username='tester')
    token = generate_jwt_token(user)

    raw = b'iam image bytes'
    b64 = base64.b64encode(raw).decode('ascii')
    data_uri = f'data:image/png;base64,{b64}'

    resp = client.post('/v1/blobs', json={'id': 'obj1', 'data': data_uri}, headers={'Authorization': f'Bearer {token}'})
    # Debug: if server returns error, print body to help diagnose (useful when running under pytest)
    if resp.status_code != 200:
        print('POST RESPONSE TEXT:', resp.text)
    assert resp.status_code == 200
    body = resp.json()
    # response 'data' may be either a dict or a simple id string depending on wrapper behavior
    data_field = body.get('data')
    if isinstance(data_field, dict):
        assert data_field.get('id') == 'obj1'
    else:
        # accept plain string id
        assert data_field == 'obj1' or data_field == {'id': 'obj1'}

    # retrieve
    resp2 = client.get('/v1/blobs/obj1', headers={'Authorization': f'Bearer {token}'})
    if resp2.status_code != 200:
        print('GET RESPONSE TEXT:', resp2.text)
    assert resp2.status_code == 200
    resp_json = resp2.json()
    # two possible shapes:
    # 1) top-level keys: {message, id, data, size, created_at}
    # 2) nested under 'data': {message, data: {id, data, size, created_at}}
    if isinstance(resp_json.get('data'), dict):
        nested = resp_json['data']
        assert nested.get('id') == 'obj1'
        assert nested.get('data') == b64
    else:
        assert resp_json.get('id') == 'obj1'
        assert resp_json.get('data') == b64
    # cleanup DB connections
    asyncio.run(close_db())