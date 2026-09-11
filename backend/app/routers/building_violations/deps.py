"""Request dependencies: database session, the authenticated user, officer profile and permission checks.

Authentication is the platform's stateless JWT Bearer scheme (OAuth2PasswordBearer; access token carries the
user's UUID in ``sub`` and the roles). Error bodies are {"detail": "..."}:
  401  no / invalid Bearer token            403  no active officer profile, or missing permission
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, HTTPException, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.core.errors import AuthError
from app.core.security import decode_token
from app.db.session import get_db
from app.db.util import to_uuid
from app.models.building_violations import User
from app.services.building_violations import access

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/building-violations/api/auth/otp/verify/", auto_error=False)

# Endpoints declare `db: DB` and receive the sync Session (SyncRouter runs them inside AsyncSession.run_sync).
DB = Annotated[Session, Depends(get_db)]
AsyncDB = Annotated[AsyncSession, Depends(get_db)]


def role_of(user):
    prof = getattr(user, "bvms_profile", None)
    return prof.role if prof and prof.active else None


async def get_current_user(request: Request, db: AsyncDB, token: str | None = Depends(oauth2_scheme)) -> User:
    if not token:
        raise AuthError()
    payload = decode_token(token, "access")
    uid = to_uuid(payload.get("sub") or payload.get("user_id"))
    user = await db.run_sync(lambda s: s.get(User, uid)) if uid else None
    if user is None or not user.is_active:
        raise AuthError("User not found")
    request.state.user = user
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_officer(user: CurrentUser) -> User:
    if not role_of(user):
        raise HTTPException(403, "No active officer profile for this module.")
    return user


Officer = Annotated[User, Depends(require_officer)]


def check_perm(db: Session, user, *codes: str) -> None:
    """Raise 403 unless the officer holds at least one of the permissions (management roles always pass)."""
    perms = access.permissions_for(db, user)
    if not any(c in perms for c in codes):
        raise HTTPException(403, f"Requires permission: {', '.join(codes)}")


def require_perm(*codes: str):
    async def dep(user: Officer, db: AsyncDB) -> User:
        await db.run_sync(lambda s: check_perm(s, user, *codes))
        return user
    return dep


def require_management(user: Officer) -> User:
    if role_of(user) not in access.MANAGEMENT_ROLES:
        raise HTTPException(403, "You do not have the required permission.")
    return user


def is_management(user) -> bool:
    return role_of(user) in access.MANAGEMENT_ROLES
