import base64
import os
import tempfile

import pytest

from apps.uploader.services import save_blob, get_blob, LocalStorage, pick_storage


def test_base64_validation_invalid():
    with pytest.raises(ValueError):
        # invalid base64
        import asyncio
        asyncio.get_event_loop().run_until_complete(save_blob('id1', 'not-base64'))


def test_local_storage_put_get(tmp_path):
    storage = LocalStorage(str(tmp_path))
    data = b'hello world'
    import asyncio
    asyncio.get_event_loop().run_until_complete(storage.put('file1', data))
    result = asyncio.get_event_loop().run_until_complete(storage.get('file1'))
    assert result == data
