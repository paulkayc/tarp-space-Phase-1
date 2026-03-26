"""
Onboarding API — connects the Session 0 agent services to HTTP endpoints.

Endpoints:
  POST   /api/v1/onboarding/message        — user message → agent reply (SSE or JSON)
  GET    /api/v1/onboarding/persona        — current persona + completeness + session status
  PATCH  /api/v1/onboarding/persona/fields — explicit field update (dot-notation path)
  POST   /api/v1/onboarding/skip           — mark session skipped
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_or_create_user
from app.db.models import ActivityLog, OnboardingMessage, OnboardingSession, User
from app.db.session import get_db
from app.observability.events import emit_event
from app.services.onboarding.extractor import extract_persona_delta
from app.services.onboarding.gap_analyzer import compute_completeness_score, find_next_gap
from app.services.onboarding.persona_crud import save_persona_delta
from app.services.onboarding.reflector import (
    generate_completion_summary,
    generate_gap_question,
    stream_completion_summary,
    stream_gap_question,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ── Request schemas ───────────────────────────────────────────────────────────

class MessageRequest(BaseModel):
    content: str


class PersonaFieldPatch(BaseModel):
    path: str   # dot-notation: "location.neighborhood"
    value: Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_or_create_session(db: Session, user: User) -> OnboardingSession:
    """
    Return the user's current active onboarding session.
    Creates a new one if none exists or if the latest is completed/skipped
    (users may restart onboarding).
    """
    session = (
        db.query(OnboardingSession)
        .filter(
            OnboardingSession.owner_id == user.id,
            OnboardingSession.status == "active",
        )
        .order_by(OnboardingSession.created_at.desc())
        .first()
    )
    if session is None:
        now = datetime.now(timezone.utc)
        session = OnboardingSession(
            owner_id=user.id,
            status="active",
            created_at=now,
            last_message_at=now,
        )
        db.add(session)
        db.commit()
        db.refresh(session)
    return session


def _save_message(
    db: Session,
    session: OnboardingSession,
    role: str,
    content: str,
    persona_delta: dict | None = None,
    completeness_after: float | None = None,
) -> None:
    now = datetime.now(timezone.utc)
    msg = OnboardingMessage(
        session_id=session.id,
        role=role,
        content=content,
        persona_delta=persona_delta or {},
        completeness_after=completeness_after,
        created_at=now,
    )
    db.add(msg)
    session.last_message_at = now
    db.commit()


def set_nested(obj: dict, path: str, value: Any) -> dict:
    """
    Pure function — apply a dot-notation path + value into a copy of obj.

    Example:
      set_nested({}, "location.neighborhood", "Montrose")
      → {"location": {"neighborhood": "Montrose"}}
    """
    result = dict(obj)
    parts = path.split(".")
    cur = result
    for part in parts[:-1]:
        cur[part] = dict(cur.get(part) or {})
        cur = cur[part]
    cur[parts[-1]] = value
    return result


# ── POST /onboarding/message ──────────────────────────────────────────────────

@router.post("/message")
async def post_onboarding_message(
    request: Request,
    body: MessageRequest,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """
    Main onboarding loop. Pipeline per message:

    1. Get or create active onboarding_session
    2. Save user message to onboarding_messages
    3. Get current persona
    4. LLM extraction → persona_delta
    5. Deep-merge + save delta
    6. Recompute completeness_score
    7. completeness < 0.7  → gap question
    8. completeness >= 0.7 and session not yet complete → completion summary
    9. session already completed → canned acknowledgement

    Supports SSE streaming when Accept: text/event-stream is set.
    SSE format: each chunk as  data: <text>\n\n
                final event:   data: [DONE]\n\n
    """
    session = _get_or_create_session(db, user)
    use_sse = "text/event-stream" in request.headers.get("accept", "")

    # 2. Save user message
    _save_message(db, session, "user", body.content)

    # 3–5. Extract delta and persist
    current_persona = dict(user.persona or {})
    was_empty = not current_persona

    delta = extract_persona_delta(body.content, current_persona)

    if delta:
        current_persona = save_persona_delta(db, user.external_user_id, delta)
        db.refresh(user)
        db.refresh(session)
        if was_empty:
            emit_event(
                "persona_created",
                {"initial_completeness_score": current_persona.get("completeness_score", 0.0)},
                owner_id=user.id,
                db=db,
            )
        else:
            emit_event(
                "persona_updated",
                {
                    "fields_added": list(delta.keys()),
                    "new_completeness_score": current_persona.get("completeness_score", 0.0),
                },
                owner_id=user.id,
                db=db,
            )

    # 6. Recompute score from persisted persona
    score = compute_completeness_score(current_persona)
    now = datetime.now(timezone.utc)

    # 9. Session already completed before this message
    if session.status == "completed":
        canned = "Your profile is set. Want to update anything?"
        _save_message(db, session, "agent", canned, {}, score)
        if use_sse:
            return StreamingResponse(
                _sse_canned(canned, score),
                media_type="text/event-stream",
            )
        return {
            "agent_message": canned,
            "persona_delta": {},
            "completeness_score": score,
            "onboarding_complete": True,
        }

    if score < 0.7:
        # 7. Gap question
        gap_field, default_question = find_next_gap(current_persona)
        if gap_field is None:
            default_question = "Tell me a bit more about yourself!"

        if use_sse:
            return StreamingResponse(
                _sse_gap(db, session, gap_field, default_question, current_persona, delta, score),
                media_type="text/event-stream",
            )

        agent_message = generate_gap_question(
            gap_field or "general", default_question, current_persona
        )
        _save_message(db, session, "agent", agent_message, delta, score)
        return {
            "agent_message": agent_message,
            "persona_delta": delta,
            "completeness_score": score,
            "onboarding_complete": False,
        }

    else:
        # 8. Completion
        agent_message = generate_completion_summary(current_persona)

        # Mark session completed and set user.onboarding_completed_at
        session.status = "completed"
        session.completed_at = now
        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = now
        db.add(session)
        db.add(user)
        db.commit()

        _save_message(db, session, "agent", agent_message, delta, score)

        emit_event(
            "onboarding_completed",
            {"final_completeness_score": score, "skipped": False},
            owner_id=user.id,
            db=db,
        )

        if use_sse:
            return StreamingResponse(
                _sse_complete(agent_message, delta, score),
                media_type="text/event-stream",
            )
        return {
            "agent_message": agent_message,
            "persona_delta": delta,
            "completeness_score": score,
            "onboarding_complete": True,
        }


# ── SSE generators ────────────────────────────────────────────────────────────

async def _sse_canned(message: str, score: float):
    yield f"data: {message}\n\n"
    yield "data: [DONE]\n\n"


async def _sse_gap(db, session, gap_field, default_question, persona, delta, score):
    full_text = ""
    async for chunk in stream_gap_question(gap_field or "general", default_question, persona):
        full_text += chunk
        yield f"data: {chunk}\n\n"
    yield "data: [DONE]\n\n"
    _save_message(db, session, "agent", full_text, delta, score)


async def _sse_complete(agent_message: str, delta: dict, score: float):
    yield f"data: {agent_message}\n\n"
    yield "data: [DONE]\n\n"


# ── GET /onboarding/persona ───────────────────────────────────────────────────

@router.get("/persona")
def get_onboarding_persona(
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """Return the current persona blob, completeness score, and session status."""
    persona = dict(user.persona or {})
    score = compute_completeness_score(persona)

    session = (
        db.query(OnboardingSession)
        .filter(OnboardingSession.owner_id == user.id)
        .order_by(OnboardingSession.created_at.desc())
        .first()
    )
    session_status = session.status if session else None

    return {
        "persona": persona,
        "completeness_score": score,
        "onboarding_completed_at": user.onboarding_completed_at,
        "session_status": session_status,
    }


# ── PATCH /onboarding/persona/fields ─────────────────────────────────────────

@router.patch("/persona/fields")
def patch_persona_field(
    body: PersonaFieldPatch,
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """
    Explicit user update of a single nested persona field using dot-notation path.
    Marks the field with source=explicit in persona metadata.

    Example body: { "path": "location.neighborhood", "value": "The Heights" }
    """
    current = dict(user.persona or {})

    # Set the value at the dot-notation path
    delta = set_nested({}, body.path, body.value)

    # Mark as explicit in _meta.source_flags
    meta = dict(current.get("_meta") or {})
    source_flags = dict(meta.get("source_flags") or {})
    source_flags[body.path] = "explicit"
    meta["source_flags"] = source_flags
    delta["_meta"] = meta

    updated_persona = save_persona_delta(db, user.external_user_id, delta)
    score = compute_completeness_score(updated_persona)

    return {
        "persona": updated_persona,
        "completeness_score": score,
        "field_updated": body.path,
        "source": "explicit",
    }


# ── POST /onboarding/skip ─────────────────────────────────────────────────────

@router.post("/skip")
def skip_onboarding(
    user: User = Depends(get_or_create_user),
    db: Session = Depends(get_db),
):
    """
    Mark onboarding as skipped.
    Sets session.status = 'skipped', user.onboarding_completed_at = now().
    Emits onboarding_completed event with skipped=true.
    """
    persona = dict(user.persona or {})
    score = compute_completeness_score(persona)
    now = datetime.now(timezone.utc)

    # Get or create session and mark skipped
    session = _get_or_create_session(db, user)
    session.status = "skipped"
    session.skipped_at = now
    db.add(session)

    user.onboarding_completed_at = now
    user.updated_at = now
    db.add(user)
    db.commit()

    emit_event(
        "onboarding_completed",
        {"final_completeness_score": score, "skipped": True},
        owner_id=user.id,
        db=db,
    )

    return {"skipped": True, "completeness_score": score}
