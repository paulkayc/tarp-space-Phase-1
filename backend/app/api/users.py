from datetime import datetime, timezone
import re

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.models import Mandate, User
from app.db.session import get_db

router = APIRouter()

E164_REGEX = re.compile(r"^\+[1-9]\d{1,14}$")


class UpdateCurrentUserRequest(BaseModel):
    display_name: str | None = None
    phone: str | None = None


def _compute_onboarding_status(db: Session, user: User) -> str:
    user_mandates = [m for m in db.query(Mandate).all() if m.owner_id == user.id]
    has_confirmed = any(m.is_active or m.confirmed_at is not None for m in user_mandates)
    if has_confirmed:
        return "mandate_confirmed"
    if user_mandates:
        return "mandate_draft"
    return "account_created"


def _serialize_user(db: Session, user: User) -> dict:
    return {
        "id": str(user.id),
        "dev_user_id": user.external_user_id,
        "email": user.email,
        "display_name": user.display_name,
        "verified_at": user.verified_at,
        "onboarding_status": _compute_onboarding_status(db, user),
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


@router.get("/me")
def get_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    return _serialize_user(db, current_user)


@router.patch("/me")
def patch_me(
    payload: UpdateCurrentUserRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if payload.phone is not None and not E164_REGEX.match(payload.phone):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "Phone number format invalid",
                "details": {"field": "phone", "expected": "E.164 format"},
            },
        )

    if payload.display_name is not None:
        current_user.display_name = payload.display_name
    if payload.phone is not None:
        current_user.phone = payload.phone

    current_user.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(current_user)
    return _serialize_user(db, current_user)
