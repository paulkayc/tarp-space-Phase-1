"""
Dev auth — local development only.

Every protected request must include: X-Dev-User-Id: <uuid-v4>
The UUID value IS the owner_id — no lookup, no token validation.

Errors:
  - Header missing  → 401 {"error": "unauthorized", "message": "X-Dev-User-Id header required"}
  - Not a valid UUID → 401 {"error": "unauthorized", "message": "X-Dev-User-Id must be a valid UUID"}
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db


def get_current_owner_id(
    x_dev_user_id: str | None = Header(None),
) -> uuid.UUID:
    """
    FastAPI dependency — extracts and validates X-Dev-User-Id header.

    Returns a UUID object. Raises 401 if missing or not a valid UUID v4.
    """
    if not x_dev_user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "X-Dev-User-Id header required",
            },
        )
    try:
        uid = uuid.UUID(x_dev_user_id)
        if uid.version != 4:
            raise ValueError("not v4")
    except (ValueError, AttributeError):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "X-Dev-User-Id must be a valid UUID",
            },
        )
    return uid


def get_or_create_user(
    owner_id: uuid.UUID = Depends(get_current_owner_id),
    db: Session = Depends(get_db),
) -> User:
    """
    FastAPI dependency — look up or create the User row for owner_id.

    On first request with a new UUID, auto-creates:
      external_user_id = str(owner_id)
      display_name     = "User <first-8-chars>"
      persona          = {}
      onboarding_completed_at = null

    Any UUID = valid user. Zero signup friction in local dev.
    """
    owner_str = str(owner_id)
    user = db.query(User).filter(User.external_user_id == owner_str).first()
    if user is None:
        now = datetime.now(timezone.utc)
        user = User(
            external_user_id=owner_str,
            display_name=f"User {owner_str[:8]}",
            persona={},
            created_at=now,
            updated_at=now,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# Backward-compatibility alias used by stub routers (conversations, mandates, etc.)
# until they are fully implemented with get_or_create_user.
def get_current_user_id(
    owner_id: uuid.UUID = Depends(get_current_owner_id),
) -> str:
    """Returns external_user_id as a string. Prefer get_or_create_user in new code."""
    return str(owner_id)
