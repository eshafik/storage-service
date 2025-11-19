from pydantic import BaseModel, Field
from typing import Optional


class BlobCreate(BaseModel):
    id: str = Field(..., min_length=1)
    data: str = Field(..., min_length=1)


class BlobResponse(BaseModel):
    id: str
    data: str
    size: int
    created_at: str


class BlobMetaOut(BaseModel):
    id: str
    size: int
    backend: Optional[str] = None
    created_at: str
