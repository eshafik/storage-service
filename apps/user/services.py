import uuid

from tortoise.exceptions import DoesNotExist
from fastapi import Request, HTTPException

from apps.user.models import User
from utils.jwt import verify_jwt_token
from utils.security import hash_password, verify_password
from typing import Optional, Tuple


async def authenticate_user(email: str, password: str) -> Optional[User]:
    try:
        user = await User.get(email=email)
    except DoesNotExist:
        return None
    if not user.password or not verify_password(password, user.password):
        return None
    return user


async def create_user(email: Optional[str] = None,
                      username: Optional[str] = None,
                      password: Optional[str] = None,
                      name: Optional[str] = None) -> User:
    hashed_pwd = password and hash_password(password) or None
    username = username or uuid.uuid4().hex
    name = name or f'Anonymous-{uuid.uuid4().hex[:5]}'
    user = await User.create(username=username, email=email, password=hashed_pwd, name=name)
    return user


async def get_user_by_email(email: str) -> Optional[User]:
    user = await User.filter(email=email).first()
    return user


async def get_user_by_username(username: str) -> Optional[User]:
    user = await User.filter(username=username).first()
    return user


async def get_or_create_user(email: str = None,
                             username: str = None,
                             name: str = None,
                             password: str = None) -> Tuple[bool, User]:
    user = None
    if email:
        user = await get_user_by_email(email=email)
    elif username:
        user = await get_user_by_username(username=username)
    if user:
        return False, user
    user = await create_user(email=email, username=username, name=name, password=password)
    return True, user


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
