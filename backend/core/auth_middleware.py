from typing import Any

from fastapi import Request
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from core.config import settings


class CredentialMiddleware(BaseHTTPMiddleware):
    """Validate bearer credentials for protected ingest routes."""

    def __init__(self, app, protected_prefixes: tuple[str, ...] = ("/api/ingest",)):
        super().__init__(app)
        self.protected_prefixes = protected_prefixes

    async def dispatch(self, request: Request, call_next):
        if not any(request.url.path.startswith(prefix) for prefix in self.protected_prefixes):
            return await call_next(request)

        authorization = request.headers.get("Authorization", "")
        if not authorization.startswith("Bearer "):
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        token = authorization.removeprefix("Bearer ").strip()
        if not token:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        try:
            claims: dict[str, Any] = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        except JWTError:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired credentials"},
                headers={"WWW-Authenticate": "Bearer"},
            )

        request.state.auth_context = claims
        return await call_next(request)