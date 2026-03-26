from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.personal_agent.memory.service import PersonalMemoryService
from app.agents.personal_agent.policy import is_memory_question, one_question_guard
from app.agents.personal_agent.prompt_builder import build_memory_reflection, default_opening_prompt
from app.core.config import settings
from app.db.models import OnboardingMessage, OnboardingSession, User
from app.services.conversation.extractor import extract_persona_and_mandate_delta
from app.services.conversation.gap_analyzer import analyze_gaps, compute_onboarding_completeness
from app.services.conversation.reflector import build_reflection


class PersonalAgentRuntime:
    def __init__(self, db: Session):
        self.db = db
        self.memory_service = PersonalMemoryService(db)

    def create_session(self, owner: User, opening_message: str | None = None) -> tuple[OnboardingSession, OnboardingMessage]:
        now = datetime.now(timezone.utc)
        session = OnboardingSession(
            owner_id=owner.id,
            status="active",
            completed_at=None,
            skipped_at=None,
            created_at=now,
            last_message_at=now,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        first_message = OnboardingMessage(
            session_id=session.id,
            role="agent",
            content=opening_message or default_opening_prompt(),
            persona_delta=None,
            completeness_after=0.0,
            token_count=None,
            created_at=now,
        )
        self.db.add(first_message)
        self.db.commit()
        self.db.refresh(first_message)
        return session, first_message

    def get_owned_session(self, owner_id: UUID, conversation_id: UUID) -> OnboardingSession:
        for session in self.db.query(OnboardingSession).all():
            if session.id == conversation_id:
                if session.owner_id != owner_id:
                    raise HTTPException(
                        status_code=403,
                        detail={"error": "forbidden", "message": "You do not own this conversation"},
                    )
                return session
        raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Conversation not found"})

    def get_messages(self, session_id: UUID) -> list[OnboardingMessage]:
        messages = [m for m in self.db.query(OnboardingMessage).all() if m.session_id == session_id]
        messages.sort(key=lambda item: item.created_at)
        return messages

    def _merge_persona(self, base: dict, delta: dict) -> dict:
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

    def run_turn(
        self,
        session: OnboardingSession,
        owner: User,
        content: str,
    ) -> tuple[OnboardingMessage, OnboardingMessage, dict, dict, dict, float, list[str], str | None, bool]:
        if session.status != "active":
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_error", "message": "Conversation is not active"},
            )

        now = datetime.now(timezone.utc)
        existing_persona = owner.persona or {}

        if is_memory_question(content):
            persona_delta = {}
            mandate_delta = {}
            merged_persona = existing_persona
            completeness_score = compute_onboarding_completeness(merged_persona)
            gap_info = analyze_gaps(merged_persona)
            memory_hits = self.memory_service.search_memories(owner.id, "preferences", limit=5)
            if memory_hits:
                rendered = "; ".join([item.content for item in memory_hits])
                agent_text = f"Here's what I remember from memory: {rendered}."
            else:
                agent_text = build_memory_reflection(merged_persona)
            is_complete = completeness_score >= settings.onboarding_completeness_threshold
        else:
            persona_delta, mandate_delta = extract_persona_and_mandate_delta(content, existing_persona)
            merged_persona = self._merge_persona(existing_persona, persona_delta)
            owner.persona = merged_persona
            self._persist_persona_memories(owner.id, persona_delta)
            completeness_score = compute_onboarding_completeness(merged_persona)
            gap_info = analyze_gaps(merged_persona)
            is_complete = completeness_score >= settings.onboarding_completeness_threshold
            if is_complete:
                agent_text = build_reflection(merged_persona)
                owner.onboarding_completed_at = now
            else:
                agent_text = gap_info["next_question"] or default_opening_prompt()

        agent_text = one_question_guard(agent_text)

        user_msg = OnboardingMessage(
            session_id=session.id,
            role="user",
            content=content,
            persona_delta=persona_delta or None,
            completeness_after=completeness_score,
            token_count=None,
            created_at=now,
        )
        agent_msg = OnboardingMessage(
            session_id=session.id,
            role="agent",
            content=agent_text,
            persona_delta=mandate_delta or None,
            completeness_after=completeness_score,
            token_count=None,
            created_at=now,
        )

        self.db.add(user_msg)
        self.db.add(agent_msg)
        session.last_message_at = now
        self.db.commit()
        self.db.refresh(user_msg)
        self.db.refresh(agent_msg)

        return (
            user_msg,
            agent_msg,
            merged_persona,
            persona_delta,
            mandate_delta,
            completeness_score,
            gap_info["gaps_remaining"],
            gap_info["next_gap"],
            is_complete,
        )

    def _persist_persona_memories(self, owner_id: UUID, persona_delta: dict) -> None:
        if not persona_delta:
            return

        for key, value in persona_delta.items():
            if value in (None, "", [], {}):
                continue
            content = f"{key}: {value}"
            self.memory_service.add_memory(
                owner_id=owner_id,
                content=content,
                tags=[key, "persona", "preferences"],
                source="inferred",
                confidence=0.8,
            )
