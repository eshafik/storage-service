# Storage Service

Simple FastAPI-based blob storage service with pluggable backends (local filesystem, database, S3-over-HTTP), metadata tracking and Bearer JWT auth.

This README explains how to set up a Python virtual environment, install dependencies, run the app, run tests, and exercise the main API flows (signup -> token -> create blob -> get blob). It also points to the interactive Swagger UI.

## Requirements

- Python 3.9+ (3.12 tested locally)
- git (optional)

This project uses the project's `requirements.txt` to install Python dependencies.

## Quickstart (local development)

1. Create and activate a virtualenv (recommended):

```bash
# create a venv in the project (example name: venv)
python3 -m venv venv

# macOS / Linux: activate
source venv/bin/activate

# Windows (PowerShell):
# .\venv\Scripts\Activate.ps1
```

2. Install dependencies:

```bash
pip install -U pip
pip install -r requirements.txt
```

3. (Optional) Configure environment variables

You can create a `.env` file at the project root to set any of the following (defaults are provided in `config/settings.py`):

```
# Database: sqlite by default, stored at project root as db.sqlite3
DATABASE_URL=sqlite:///db.sqlite3

# Storage backend: use one of LOCAL, DB or S3
# - LOCAL: store files on local filesystem (default)
# - DB: store binary blobs in the database
# - S3: store objects on an S3-compatible HTTP endpoint (set S3_* variables)
STORAGE_BACKEND=LOCAL

# Local storage path (used when STORAGE_BACKEND=local)
LOCAL_STORAGE_PATH=./storage

# S3 settings (used when STORAGE_BACKEND=s3)
S3_ENDPOINT=
S3_BUCKET=
S3_ACCESS_KEY=
S3_SECRET_KEY=
S3_REGION=

# FastAPI environment
FASTAPI_ENV=development
```

4. Run the development server

This project provides a small `manage.py` helper. To run the app in development (with reload):

```bash
python manage.py runserver --host 127.0.0.1 --port 8000
```

By default `DEBUG` is enabled when `FASTAPI_ENV=development`, so the server will start with auto-reload.

When running in production, omit `--host`/`--port` or set `FASTAPI_ENV=production` and the server will bind to `0.0.0.0`.

## Interactive API docs (Swagger / ReDoc)

When the server is running, open the interactive API docs in your browser:

- Swagger UI: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc

If you expose the service on a different host/port, replace `127.0.0.1:8000` accordingly. If you run behind a TLS-terminating proxy with HTTPS, the docs URL will typically be `https://your-host/docs`.

## Run tests

Run the pytest suite (this prints a compact report with summary counts):

```bash
pytest -r a
```

If you prefer dot-style progress with the summary at the end:

```bash
pytest -q -r a
```

Notes:

- A `pytest.ini` file is included with sensible defaults for test discovery and a filter to reduce a noisy third-party deprecation warning.

## API Usage Examples

Below are example curl sequences you can use to exercise the service. They assume the server is running on `127.0.0.1:8000`.

1. Sign up (create a user)

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"s3cret"}' | jq .
```

Response contains a token. The project uses a small response wrapper that may put payload under `data` or return top-level `token`. To extract the token robustly with `jq`:

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/signup \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"s3cret"}' \
  | jq -r '.data.token // .token')
echo $TOKEN
```

2. Obtain a token (alternate flow / login)

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/v1/token \
  -H "Content-Type: application/json" \
  -d '{"email":"alice@example.com","password":"s3cret"}' \
  | jq -r '.data.token // .token')
```

3. Create a blob

The `POST /v1/blobs` endpoint accepts a JSON body with an `id` and `data` (base64 string). Example uses a short text blob encoded in base64.

Important: the `data` value should be the raw base64-encoded payload only — do NOT include the data-URI prefix `data:application/octet-stream;base64,` in the `data` field. The server will accept valid base64 only. (If you have a data-URI on the client side, strip the `data:...;base64,` prefix before sending.)

```bash
BASE64_DATA=$(printf "hello world" | base64)
curl -s -X POST http://127.0.0.1:8000/v1/blobs \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d "{\"id\": \"my-object-1\", \"data\": \"${BASE64_DATA}\"}" | jq .
```

Successful response includes the assigned `id`. If the ID already exists or the data is invalid you'll get a 400 error.

4. Get a blob

```bash
curl -s -X GET http://127.0.0.1:8000/v1/blobs/my-object-1 \
  -H "Authorization: Bearer $TOKEN" | jq .
```

The response contains the stored base64 data and metadata like size and created_at. You can decode the data to a file like this:

```bash
curl -s -X GET http://127.0.0.1:8000/v1/blobs/my-object-1 \
  -H "Authorization: Bearer $TOKEN" \
  | jq -r '.data.data // .data' | base64 --decode > out.bin
```

Notes about the API:

- Endpoints are protected with a simple Bearer JWT. Use the token returned by signup or login.
- Blob `data` must be a valid base64-encoded payload (data URIs are supported, e.g. `data:application/octet-stream;base64,...`).

## Configuration / Environment variables

Key environment variables (see `config/settings.py` for defaults):

- `DATABASE_URL` — Tortoise DB connection (default: `sqlite://db.sqlite3`)
- `STORAGE_BACKEND` — choose one of `LOCAL`, `DB`, or `S3` (default: `LOCAL`):
  - `LOCAL` — store blobs on the local filesystem (use `LOCAL_STORAGE_PATH` to control path)
  - `DB` — store binary data in the database alongside metadata
  - `S3` — store objects on an S3-compatible HTTP endpoint (configure S3\_\* variables)
- `LOCAL_STORAGE_PATH` — directory for local backend (default: `./storage`)
- `S3_ENDPOINT`, `S3_BUCKET`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_REGION` — used by the S3 HTTP backend
- `FASTAPI_ENV` — `development` or `production` (controls `DEBUG` behavior and reload)

Blob payload note:

- When calling `POST /v1/blobs`, pass the `data` field as raw base64 (no `data:...;base64,` prefix). The service expects valid base64. Although some helper code may tolerate data-URIs, clients should send the base64 payload only.

## Running in Docker (optional)

You can containerize the app with a simple `Dockerfile` that installs requirements and runs `uvicorn main:app` (not included by default here). If you deploy behind a TLS-terminating proxy you can expose the Swagger UI at `https://your-host/docs`.

## Troubleshooting

- If tests print a `DeprecationWarning` coming from `passlib` on Python 3.12, the project includes a `pytest.ini` filter to suppress that noisy warning during tests. Long-term you can upgrade `passlib`.
- If you see database write errors while running tests, ensure the `DATABASE_URL` points to a writable path (tests default to a temp sqlite file).
- If you can't authenticate, ensure you pass the `Authorization: Bearer <token>` header exactly.

## Contributing

Contributions welcome. Please open issues or PRs. If you add a new storage backend, implement the `StorageInterface` in `apps/uploader/services.py` and add configuration wiring.

---

If you want, I can also add a `Dockerfile` and a `docker-compose.yml` example to run the app + a local MinIO test S3 backend for S3 integration tests — tell me and I will add them.
