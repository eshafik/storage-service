# middleware.py
import time
from typing import Dict, Tuple, Any
from fastapi import HTTPException, Request
from collections import defaultdict, deque
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class CustomMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Modify the request here (e.g., add custom headers, authentication, etc.)
        request.state.custom_attribute = "Custom value"

        response: Response = await call_next(request)
        # Modify the response here (if needed)
        return response
