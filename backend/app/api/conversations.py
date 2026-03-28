"""
Conversations API (Option A): onboarding conversation flow.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.agents.mandate_agent.gap_analyzer import analyze_mandate_gaps, compute_mandate_completeness
from app.agents.mandate_agent.prompt_builder import build_mandate_reflection
from app.core.auth import get_current_user
from app.core.config import settings
from app.db.models import OnboardingMessage, OnboardingSession, User
from app.db.session import get_db
from app.services.conversation.extractor import extract_mandate_delta

router = APIRouter()


class CreateConversationRequest(BaseModel):
    opening_message: str | None = None


class SendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


def _not_found() -> None:
    raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Conversation not found"})


def _forbidden() -> None:
    raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "You do not own this conversation"})


def _get_onboarding_session(db: Session, conversation_id: UUID) -> OnboardingSession | None:
    for session in db.query(OnboardingSession).all():
        if session.id == conversation_id:
            return session
    return None


def _get_owned_session_or_raise(db: Session, conversation_id: UUID, owner_id: UUID) -> OnboardingSession:
    session = _get_onboarding_session(db, conversation_id)
    if session is None:
        _not_found()
    if session.owner_id != owner_id:
        _forbidden()
    return session


def _get_session_messages(db: Session, session_id: UUID) -> list[OnboardingMessage]:
    messages = [m for m in db.query(OnboardingMessage).all() if m.session_id == session_id]
    messages.sort(key=lambda item: item.created_at)
    return messages


def _merge_persona(base: dict, delta: dict) -> dict:
    merged = dict(base)
    for key, value in delta.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            nested = dict(existing)
            nested.update(value)
            merged[key] = nested
        elif isinstance(existing, list) and isinstance(value, list):
            out = list(existing)
            for item in value:
                if item not in out:
                    out.append(item)
            merged[key] = out
        else:
            merged[key] = value
    return merged


def _serialize_message(message: OnboardingMessage) -> dict:
    return {
        "id": str(message.id),
        "role": message.role,
        "content": message.content,
        "persona_delta": message.persona_delta,
        "completeness_after": float(message.completeness_after or 0.0),
        "created_at": message.created_at,
    }


def _new_agent_prompt() -> str:
    return "Hi, I am your Tarp-Space onboarding agent. What are you trying to buy, sell, or find right now?"


@router.post("")
def create_conversation(
    payload: CreateConversationRequest | None = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    session = OnboardingSession(
        owner_id=current_user.id,
        status="active",
        completed_at=None,
        skipped_at=None,
        created_at=now,
        last_message_at=now,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    opening = (payload.opening_message if payload else None) or _new_agent_prompt()
    first_agent_message = OnboardingMessage(
        session_id=session.id,
        role="agent",
        content=opening,
        persona_delta=None,
        completeness_after=0.0,
        token_count=None,
        created_at=now,
    )
    db.add(first_agent_message)
    db.commit()
    db.refresh(first_agent_message)

    return {
        "conversation": {
            "id": str(session.id),
            "status": session.status,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "completed_at": session.completed_at,
        },
        "agent_message": _serialize_message(first_agent_message),
        "persona": current_user.persona or {},
    }


@router.get("/{conversation_id}")
def get_conversation(
    conversation_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_owned_session_or_raise(db, conversation_id, current_user.id)
    messages = _get_session_messages(db, session.id)
    return {
        "conversation": {
            "id": str(session.id),
            "status": session.status,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "completed_at": session.completed_at,
        },
        "messages": [_serialize_message(m) for m in messages],
        "total": len(messages),
        "persona": current_user.persona or {},
    }


@router.post("/{conversation_id}/messages")
def send_message(
    conversation_id: UUID,
    payload: SendMessageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    session = _get_owned_session_or_raise(db, conversation_id, current_user.id)
    if session.status != "active":
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "Conversation is not active"},
        )

    now = datetime.now(timezone.utc)
    existing_persona = current_user.persona or {}
    # Legacy endpoint: extract mandate fields and store them on user.persona
    # so that mandate prefill still works for older integrations.
    try:
        mandate_delta = extract_mandate_delta(payload.content, {})
    except Exception:
        mandate_delta = {}
    persona_delta = mandate_delta  # kept for backward compat field name in response
    merged_persona = _merge_persona(existing_persona, mandate_delta)
    current_user.persona = merged_persona

    completeness_score = compute_mandate_completeness(merged_persona)
    gap_info = analyze_mandate_gaps(merged_persona)
    is_complete = completeness_score >= settings.onboarding_completeness_threshold

    user_msg = OnboardingMessage(
        session_id=session.id,
        role="user",
        content=payload.content,
        persona_delta=persona_delta or None,
        completeness_after=completeness_score,
        token_count=None,
        created_at=now,
    )
    db.add(user_msg)

    if is_complete:
        agent_text = build_mandate_reflection(merged_persona)
        session.status = "completed"
        session.completed_at = now
        current_user.onboarding_completed_at = now
    else:
        agent_text = gap_info["next_question"] or _new_agent_prompt()


    agent_msg = OnboardingMessage(
        session_id=session.id,
        role="agent",
        content=agent_text,
        persona_delta=mandate_delta or None,
        completeness_after=completeness_score,
        token_count=None,
        created_at=now,
    )
    db.add(agent_msg)
    session.last_message_at = now
    db.commit()
    db.refresh(user_msg)
    db.refresh(agent_msg)

    return {
        "conversation": {
            "id": str(session.id),
            "status": session.status,
            "created_at": session.created_at,
            "last_message_at": session.last_message_at,
            "completed_at": session.completed_at,
        },
        "user_message": _serialize_message(user_msg),
        "agent_message": _serialize_message(agent_msg),
        "persona_delta": persona_delta,
        "mandate_delta": mandate_delta,
        "persona": merged_persona,
        "completeness_score": completeness_score,
        "gaps_remaining": gap_info["gaps_remaining"],
        "next_gap": gap_info["next_gap"],
        "elicitation_complete": is_complete,
    }
