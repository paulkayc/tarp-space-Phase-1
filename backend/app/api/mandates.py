from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.db.models import Mandate, User
from app.db.session import get_db
from app.agents.mandate_agent.gap_analyzer import compute_mandate_completeness, derive_mandate_state
from app.services.mandate.crud import prefill_mandate_from_persona


def compute_completeness_score(mandate: Mandate) -> float:  # type: ignore[type-arg]
    return compute_mandate_completeness(derive_mandate_state(mandate))

router = APIRouter()


MOCK_SEARCH_RESPONSE = {
    "search_id": "00000000-0000-0000-0000-000000000001",
    "mandate_version": 1,
    "results": [
        {
            "listing_id": "00000000-0000-0000-0000-000000000002",
            "alignment_score": 0.91,
            "price": 420.00,
            "within_mandate": True,
            "matched_dimensions": ["style", "condition", "location", "price"],
            "explanation": "Mock result: mid-century sofa, like-new, Montrose, $80 below ceiling.",
            "escalation": None,
        },
        {
            "listing_id": "00000000-0000-0000-0000-000000000003",
            "alignment_score": 0.78,
            "price": 380.00,
            "within_mandate": True,
            "matched_dimensions": ["style", "location"],
            "explanation": "Mock result: matches style and location.",
            "escalation": None,
        },
    ],
    "escalations": [
        {
            "listing_id": "00000000-0000-0000-0000-000000000004",
            "alignment_score": 0.82,
            "price": 560.00,
            "within_mandate": False,
            "threshold_delta": 60.00,
            "question": "This listing is $60 above your ceiling but matches on style and condition. Want me to explore it?",
        }
    ],
}


CONFIRM_LOW_SCORE_RESPONSE = {
    "error": "validation_error",
    "message": "Mandate completeness score too low to confirm",
    "details": {"current_score": 0.0, "required_score": 0.70},
}


def _serialize_mandate(mandate: Mandate) -> dict:
    status = "confirmed" if (mandate.is_active or mandate.confirmed_at is not None) else "draft"
    return {
        "id": str(mandate.id),
        "owner_id": str(mandate.owner_id),
        "intent_type": mandate.intent_type,
        "vertical": mandate.vertical,
        "category": mandate.category,
        "description": mandate.description,
        "hard_constraints": mandate.hard_constraints or [],
        "negotiation_range": mandate.negotiation_range or [],
        "soft_preferences": mandate.soft_preferences or [],
        "dealbreakers": mandate.dealbreakers or [],
        "escalation_triggers": mandate.escalation_triggers or [],
        "autonomy_level": mandate.autonomy_level,
        "completeness_score": float(mandate.completeness_score or 0.0),
        "status": status,
        "version": mandate.version,
        "confirmed_at": mandate.confirmed_at,
        "created_at": mandate.created_at,
        "updated_at": mandate.updated_at,
    }


def _get_mandate(db: Session, mandate_id: UUID) -> Mandate | None:
    return db.query(Mandate).filter_by(id=mandate_id).first()


def _get_owned_mandate_or_raise(db: Session, mandate_id: UUID, owner_id: UUID) -> Mandate:
    mandate = _get_mandate(db, mandate_id)
    if mandate is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Mandate not found"},
        )
    if mandate.owner_id != owner_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You do not own this mandate"},
        )
    return mandate


@router.get("")
def list_mandates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandates = db.query(Mandate).filter_by(owner_id=current_user.id).all()
    mandates.sort(key=lambda item: item.created_at, reverse=True)
    return {
        "mandates": [_serialize_mandate(m) for m in mandates],
        "next_cursor": None,
        "total": len(mandates),
    }


@router.post("", status_code=201)
def create_mandate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    mandate = Mandate(
        owner_id=current_user.id,
        hard_constraints=[],
        negotiation_range=[],
        soft_preferences=[],
        dealbreakers=[],
        escalation_triggers=[],
        completeness_score=0.0,
        is_active=False,
        is_archived=False,
        version=1,
        created_at=now,
        updated_at=now,
    )
    prefill_mandate_from_persona(mandate, current_user)
    mandate.completeness_score = compute_completeness_score(mandate)
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    return _serialize_mandate(mandate)


@router.get("/{mandate_id}")
def get_mandate(
    mandate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandate = _get_owned_mandate_or_raise(db, mandate_id, current_user.id)
    return _serialize_mandate(mandate)


@router.post("/{mandate_id}/confirm")
def confirm_mandate(
    mandate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandate = _get_owned_mandate_or_raise(db, mandate_id, current_user.id)
    mandate.completeness_score = compute_completeness_score(mandate)
    current_score = float(mandate.completeness_score or 0.0)
    if current_score < settings.completeness_threshold:
        return JSONResponse(
            status_code=422,
            content={
                **CONFIRM_LOW_SCORE_RESPONSE,
                "details": {
                    "current_score": round(current_score, 3),
                    "required_score": round(float(settings.completeness_threshold), 2),
                },
            },
        )

    now = datetime.now(timezone.utc)
    mandate.is_active = True
    mandate.confirmed_at = now
    mandate.updated_at = now
    db.commit()
    db.refresh(mandate)
    return _serialize_mandate(mandate)


@router.post("/{mandate_id}/search")
def search_mandate(
    mandate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandate = _get_owned_mandate_or_raise(db, mandate_id, current_user.id)
    response = dict(MOCK_SEARCH_RESPONSE)
    response["mandate_version"] = mandate.version
    response["mandate_id"] = str(mandate.id)
    return response
