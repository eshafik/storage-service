
# uploader/routers.py
from fastapi import APIRouter
from utils.response_wrapper import response_wrapper
from .views import create_blob, retrieve_blob

router = APIRouter()

router.post("/api/v1/blobs")(response_wrapper(create_blob))
router.get("/api/v1/blobs/{blob_id}")(response_wrapper(retrieve_blob))
