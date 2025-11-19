from fastapi import HTTPException, Request
from apps.uploader.schema import BlobCreate
from apps.uploader.services import save_blob, get_blob
from utils.jwt import verify_jwt_token


async def _require_auth(request: Request):
    """Simple bearer token check using utils.jwt.verify_jwt_token"""
    auth = request.headers.get('authorization') or request.headers.get('Authorization')
    if not auth or not auth.lower().startswith('bearer '):
        raise HTTPException(status_code=401, detail='Missing or invalid authorization header')
    token = auth.split(None, 1)[1].strip()
    user = verify_jwt_token(token)
    if not user:
        raise HTTPException(status_code=401, detail='Invalid token')
    return user


async def create_blob(request: Request, data: BlobCreate):
    # auth
    await _require_auth(request)
    payload = data.model_dump()
    try:
        await save_blob(payload['id'], payload['data'])
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    return {'id': payload['id'], 'message': 'Blob stored successfully'}


async def retrieve_blob(request: Request, blob_id: str):
    await _require_auth(request)
    blob = await get_blob(blob_id)
    if not blob:
        raise HTTPException(status_code=404, detail='Blob not found')
    return blob
