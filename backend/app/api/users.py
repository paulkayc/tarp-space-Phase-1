"""
User and Agent endpoints — CONTRACTS.md Phase 1.

GET   /api/v1/users/me      — fetch (or auto-create) the current user
PATCH /api/v1/users/me      — update display_name / phone / email
GET   /api/v1/agents/me     — fetch agent status for the current user
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_or_create_user
from app.db.models import Mandate, OnboardingSession, User
from app.db.session import get_db

router = APIRouter(tags=["users"])
agents_router = APIRouter(tags=["agents"])

_E164_RE = re.compile(r"^\+[1-9]\d{6,14}$")


# ── Helpers ───────────────────────────────────────────────────────────────────

def _onboarding_status(user: User, db: Session) -> str:
    if user.onboarding_completed_at is not None:
        return "completed"
    persona = dict(user.persona) if user.persona else {}
    score = float(persona.get("completeness_score", 0.0))
    if score > 0.0:
        return "in_progress"
    has_active = (
        db.query(OnboardingSession)
        .filter(
            OnboardingSession.owner_id == user.id,
            OnboardingSession.status == "active",
        )
        .first()
        is not None
    )
    if has_active:
        return "in_progress"
    return "account_created"


def _user_response(user: User, db: Session) -> dict[str, Any]:
    persona = dict(user.persona) if user.persona else {}
    score = float(persona.get("completeness_score", 0.0))
    return {
        "id": str(user.id),
        "dev_user_id": user.external_user_id,
        "email": user.email,
        "display_name": user.display_name,
        "phone": user.phone,
        "sex": user.sex,
        "location_raw": user.location_raw,
        "onboarding_completed_at": user.onboarding_completed_at,
        "onboarding_status": _onboarding_status(user, db),
        "persona_completeness": score,
        "created_at": user.created_at,
        "updated_at": user.updated_at,
    }


# ── GET /users/me ─────────────────────────────────────────────────────────────

@router.get("/users/me")
def get_me(
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """Return current user profile. Auto-creates a user row on first call."""
    return _user_response(user, db)


# ── PATCH /users/me ───────────────────────────────────────────────────────────

class UserPatch(BaseModel):
    display_name: str | None = None
    phone: str | None = None
    email: str | None = None


@router.patch("/users/me")
def patch_me(
    body: UserPatch,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """Update display_name, phone, and/or email. Phone validated as E.164."""
    if body.phone is not None and not _E164_RE.match(body.phone):
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": "phone must be in E.164 format (e.g. +12125551234)",
            },
        )

    now = datetime.now(timezone.utc)
    if body.display_name is not None:
        user.display_name = body.display_name
    if body.phone is not None:
        user.phone = body.phone
    if body.email is not None:
        user.email = body.email
    user.updated_at = now

    db.add(user)
    db.commit()
    db.refresh(user)
    return _user_response(user, db)


# ── GET /agents/me ────────────────────────────────────────────────────────────

@agents_router.get("/agents/me")
def get_agent_me(
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """
    Return agent status for the current user.
    Phase 1: id == owner_id, reputation_score = 0.5 (static),
             completed_negotiation_count = 0 (static).
    """
    active_mandates = (
        db.query(Mandate)
        .filter(Mandate.owner_id == user.id, Mandate.is_active.is_(True))
        .all()
    )
    active_count = len(active_mandates)
    status = "active" if active_count > 0 else "inactive"

    return {
        "id": str(user.id),
        "owner_id": str(user.id),
        "status": status,
        "reputation_score": 0.5,
        "active_mandate_count": active_count,
        "completed_negotiation_count": 0,
        "created_at": user.created_at,
    }
