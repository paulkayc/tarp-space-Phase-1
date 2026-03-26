"""
Onboarding API — ARCHITECTURE.md / onboarding session spec.

Endpoints:
  POST   /api/v1/onboarding/message        — send user message, get agent reply (SSE or JSON)
  GET    /api/v1/onboarding/persona        — current persona + completeness
  PATCH  /api/v1/onboarding/persona/fields — explicit field update (dot-notation path)
  POST   /api/v1/onboarding/skip           — mark onboarding as skipped
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.db.models import ActivityLog, User
from app.db.session import get_db
from app.services.onboarding.extractor import extract_persona_delta
from app.services.onboarding.gap_analyzer import compute_completeness_score, find_next_gap
from app.services.onboarding.persona_crud import get_persona, save_persona_delta
from app.services.onboarding.reflector import (
    generate_completion_summary,
    generate_gap_question,
    stream_completion_summary,
    stream_gap_question,
)

router = APIRouter(prefix="/onboarding", tags=["onboarding"])


# ── Request / Response schemas ────────────────────────────────────────────────

class MessageRequest(BaseModel):
    content: str
    session_id: str | None = None


class PersonaFieldPatch(BaseModel):
    path: str          # dot-notation: "preferences.style_affinities"
    value: Any


# ── Helpers ───────────────────────────────────────────────────────────────────

def _get_user_or_404(db: Session, owner_id: str) -> User:
    user = db.query(User).filter(User.external_user_id == owner_id).first()
    if not user:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "User not found", "details": {}},
        )
    return user


def _build_nested_delta(dot_path: str, value: Any) -> dict:
    """Convert a dot-notation path + value into a nested dict delta."""
    parts = dot_path.split(".")
    delta: dict = {}
    cur = delta
    for i, part in enumerate(parts):
        if i == len(parts) - 1:
            cur[part] = value
        else:
            cur[part] = {}
            cur = cur[part]
    return delta


async def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


# ── POST /onboarding/message ──────────────────────────────────────────────────

@router.post("/message")
async def post_onboarding_message(
    request: Request,
    body: MessageRequest,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Main onboarding loop.

    Pipeline per message:
      a. Get current persona
      b. LLM extraction pass → persona delta
      c. Deep-merge + save delta
      d. Recompute completeness
      e. If completeness < 0.7: find gap → stream/return gap question
      f. If completeness >= 0.7: stream/return completion summary
      g. If already completed: return short acknowledgement

    Supports SSE streaming when Accept: text/event-stream is set.
    SSE event shapes:
      {"type": "token",  "content": "<text chunk>"}
      {"type": "done",   "agent_message": "<full text>", "persona_delta": {...},
                         "completeness_score": 0.x, "onboarding_complete": bool}
    """
    user = _get_user_or_404(db, owner_id)
    use_sse = "text/event-stream" in request.headers.get("accept", "")

    # g. Already completed
    if user.onboarding_completed_at is not None:
        payload = {
            "agent_message": "Your profile is all set. Want to update anything?",
            "persona_delta": {},
            "completeness_score": compute_completeness_score(user.persona or {}),
            "onboarding_complete": True,
        }
        if use_sse:
            async def _already_done():
                yield await _sse_event({"type": "token", "content": payload["agent_message"]})
                yield await _sse_event({"type": "done", **payload})
            return StreamingResponse(_already_done(), media_type="text/event-stream")
        return payload

    # b. Extraction pass (LLM call #1 — sync, structured JSON, not streamed)
    current_persona = dict(user.persona or {})
    delta = extract_persona_delta(body.content, current_persona)

    # c. Save delta
    if delta:
        current_persona = save_persona_delta(db, owner_id, delta)
        db.refresh(user)  # pick up onboarding_completed_at if set by save

    # d. Recompute completeness
    score = compute_completeness_score(current_persona)

    now = datetime.now(timezone.utc)

    if score < 0.7:
        # e. Gap question (LLM call #2)
        gap_field, default_question = find_next_gap(current_persona)
        if gap_field is None:
            default_question = "Tell me a bit more about yourself!"

        if use_sse:
            return StreamingResponse(
                _stream_gap_response(gap_field, default_question, current_persona, delta, score),
                media_type="text/event-stream",
            )

        agent_message = generate_gap_question(
            gap_field or "general", default_question, current_persona
        )
        return {
            "agent_message": agent_message,
            "persona_delta": delta,
            "completeness_score": score,
            "onboarding_complete": False,
        }

    else:
        # f. Completion summary (LLM call #2)
        if user.onboarding_completed_at is None:
            user.onboarding_completed_at = now
            db.add(
                ActivityLog(
                    owner_id=user.id,
                    event_type="onboarding_completed",
                    payload={"final_completeness_score": score, "skipped": False},
                    created_at=now,
                )
            )
            db.commit()

        if use_sse:
            return StreamingResponse(
                _stream_complete_response(current_persona, delta, score),
                media_type="text/event-stream",
            )

        agent_message = generate_completion_summary(current_persona)
        return {
            "agent_message": agent_message,
            "persona_delta": delta,
            "completeness_score": score,
            "onboarding_complete": True,
        }


async def _stream_gap_response(gap_field, default_question, persona, delta, score):
    full_text = ""
    async for chunk in stream_gap_question(gap_field or "general", default_question, persona):
        full_text += chunk
        yield await _sse_event({"type": "token", "content": chunk})
    yield await _sse_event(
        {
            "type": "done",
            "agent_message": full_text,
            "persona_delta": delta,
            "completeness_score": score,
            "onboarding_complete": False,
        }
    )


async def _stream_complete_response(persona, delta, score):
    full_text = ""
    async for chunk in stream_completion_summary(persona):
        full_text += chunk
        yield await _sse_event({"type": "token", "content": chunk})
    yield await _sse_event(
        {
            "type": "done",
            "agent_message": full_text,
            "persona_delta": delta,
            "completeness_score": score,
            "onboarding_complete": True,
        }
    )


# ── GET /onboarding/persona ───────────────────────────────────────────────────

@router.get("/persona")
def get_onboarding_persona(
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Return the current persona blob with completeness_score and
    onboarding_completed_at (null until threshold reached or skipped).
    """
    user = _get_user_or_404(db, owner_id)
    persona = dict(user.persona or {})
    return {
        "persona": persona,
        "completeness_score": compute_completeness_score(persona),
        "onboarding_completed_at": user.onboarding_completed_at,
    }


# ── PATCH /onboarding/persona/fields ─────────────────────────────────────────

@router.patch("/persona/fields")
def patch_persona_field(
    body: PersonaFieldPatch,
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Explicit user update of a single nested persona field using dot-notation path.
    Updates are tagged source="explicit" in the activity log.

    Example body: { "path": "location.neighborhood", "value": "The Heights" }
    """
    _get_user_or_404(db, owner_id)

    nested_delta = _build_nested_delta(body.path, body.value)
    updated_persona = save_persona_delta(db, owner_id, nested_delta)
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
    owner_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    """
    Mark onboarding as skipped. Sets onboarding_completed_at immediately
    at whatever completeness_score the persona currently has.
    User can return and complete it later via /onboarding.
    """
    user = _get_user_or_404(db, owner_id)
    persona = dict(user.persona or {})
    score = compute_completeness_score(persona)
    now = datetime.now(timezone.utc)

    user.onboarding_completed_at = now
    user.updated_at = now
    db.add(
        ActivityLog(
            owner_id=user.id,
            event_type="onboarding_completed",
            payload={"final_completeness_score": score, "skipped": True},
            created_at=now,
        )
    )
    db.commit()

    return {"skipped": True, "completeness_score": score}
