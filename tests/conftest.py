import os
import warnings
import shutil
from pathlib import Path

import pytest

# Suppress specific third-party deprecation warnings that surface during test collection
warnings.filterwarnings(
    "ignore",
    message="crypt is deprecated",
    category=DeprecationWarning,
    module=r"passlib.utils",
)


@pytest.fixture(autouse=True, scope='session')
def setup_test_env(tmp_path_factory):
    """Set environment defaults before app modules are imported by tests.

    - Use a sqlite file for Tortoise DB to avoid external DB dependencies
    - Force local storage backend by default
    """
    # Use a temporary directory for test DB to avoid permission/disk I/O issues
    db_dir = tmp_path_factory.mktemp('db')
    db_path = db_dir / 'test_db.sqlite3'
    os.environ.setdefault('DATABASE_URL', f'sqlite://{db_path}')
    # Storage backend defaults
    os.environ.setdefault('STORAGE_BACKEND', 'local')
    storage_dir = tmp_path_factory.mktemp('storage')
    os.environ.setdefault('LOCAL_STORAGE_PATH', str(storage_dir))

    # Provide S3 env defaults (if tests or code reference them)
    os.environ.setdefault('S3_ENDPOINT', '')
    os.environ.setdefault('S3_BUCKET', '')
    os.environ.setdefault('S3_ACCESS_KEY', '')
    os.environ.setdefault('S3_SECRET_KEY', '')

    # Clean any leftover test DB/storage before running tests
    try:
        if db_path.exists():
            db_path.unlink()
    except Exception:
        pass

    yield

    # Teardown: remove test DB and storage directories
    try:
        if db_path.exists():
            db_path.unlink()
    except Exception:
        pass
    try:
        shutil.rmtree(str(storage_dir), ignore_errors=True)
    except Exception:
        pass
