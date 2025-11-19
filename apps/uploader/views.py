from fastapi import HTTPException, Request
from apps.uploader.schema import BlobCreate
from apps.uploader.services import save_blob, get_blob
from apps.user.services import _require_auth


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
