"""JWT access / refresh tokens (PyJWT), same shape as the MCG platform's central JWT service:

    {"sub": "<user uuid>", "roles": ["JE"], "token_type": "access", "exp": ..., "iat": ..., "jti": "..."}

``user_id`` is carried as well so tokens minted by the previous edition of the module keep working.
Lifetimes: ACCESS_TOKEN_EXPIRE_MINUTES (default 720 = 12 h) and REFRESH_TOKEN_EXPIRE_MINUTES (default 30 days).
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.errors import AuthError
from app.core.timeutil import now


def _make(user_id, token_type: str, lifetime: timedelta, roles=()) -> str:
    t = now()
    payload = {"sub": str(user_id), "user_id": str(user_id), "roles": list(roles), "token_type": token_type,
               "exp": int((t + lifetime).timestamp()), "iat": int(t.timestamp()), "jti": uuid.uuid4().hex}
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_access_token(user_id, roles=()) -> str:
    return _make(user_id, "access", timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES), roles)


def create_refresh_token(user_id, roles=()) -> str:
    return _make(user_id, "refresh", timedelta(minutes=settings.REFRESH_TOKEN_EXPIRE_MINUTES), roles)


def decode_token(token: str, expected_type: str = "access") -> dict:
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise AuthError("Token is expired")
    except jwt.PyJWTError:
        raise AuthError("Given token not valid for any token type")
    if payload.get("token_type", "access") != expected_type or not (payload.get("sub") or payload.get("user_id")):
        raise AuthError("Token has wrong type")
    return payload
