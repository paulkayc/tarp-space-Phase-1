"""
Mandate Agent runtime.

Owns a specific user request (buy/sell/service) and iterates through mandate
gap questions until the mandate is complete.  Uses the existing Conversation
and Message DB models.  Reads persona memory (read-only) to pre-populate
defaults such as home_city → location.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.mandate_agent.extractor import extract_mandate_delta
from app.agents.mandate_agent.gap_analyzer import (
    analyze_mandate_gaps,
    apply_delta_to_mandate,
    compute_mandate_completeness,
    derive_mandate_state,
)
from app.agents.mandate_agent.prompt_builder import (
    build_mandate_reflection,
    default_mandate_opening_prompt,
)
from app.agents.personal_agent.memory.service import PersonalMemoryService
from app.core.config import settings
from app.db.models import Conversation, Mandate, Message


class MandateAgentRuntime:
    def __init__(self, db: Session):
        self.db = db
        self.memory_service = PersonalMemoryService(db)

    # ------------------------------------------------------------------
    # Persona context
    # ------------------------------------------------------------------

    def _load_persona_context(self, owner_id: UUID) -> dict:
        """Read personal profile fields from memory snippets (read-only)."""
        memories = self.memory_service.list_memories(owner_id=owner_id)
        context: dict = {}
        _persona_fields = {"name", "home_city", "communication_style", "general_interests", "deal_sensitivity"}
        for memory in memories:
            tags = set(memory.tags or [])
            field = tags & _persona_fields
            if field:
                key = next(iter(field))
                # Content format: "key: value"
                if ":" in memory.content:
                    _, _, raw_value = memory.content.partition(":")
                    context[key] = raw_value.strip()
        return context

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(
        self,
        owner_id: UUID,
        persona_context: dict | None = None,
    ) -> tuple[Conversation, Mandate, Message]:
        now = datetime.now(timezone.utc)
        persona_context = persona_context or self._load_persona_context(owner_id)

        mandate = Mandate(
            id=uuid4(),
            owner_id=owner_id,
            hard_constraints=[],
            negotiation_range=[],
            soft_preferences=[],
            dealbreakers=[],
            escalation_triggers=[],
            autonomy_level="escalate_key_points",
            completeness_score=0.0,
            is_active=False,
            is_archived=False,
            version=1,
            created_at=now,
            updated_at=now,
        )
        # Pre-fill location from home_city if available
        home_city = persona_context.get("home_city")
        if home_city:
            mandate.hard_constraints = [{"field": "location", "value": home_city}]

        self.db.add(mandate)
        self.db.commit()
        self.db.refresh(mandate)

        conversation = Conversation(
            id=uuid4(),
            owner_id=owner_id,
            mandate_id=mandate.id,
            status="active",
            created_at=now,
            last_message_at=now,
        )
        self.db.add(conversation)
        self.db.commit()
        self.db.refresh(conversation)

        opening_text = default_mandate_opening_prompt(persona_context)
        opening_msg = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="agent",
            content=opening_text,
            mandate_delta=None,
            completeness_after=0.0,
            gaps_remaining=list(derive_mandate_state(mandate).keys()),
            created_at=now,
            token_count=None,
        )
        self.db.add(opening_msg)
        self.db.commit()
        self.db.refresh(opening_msg)

        return conversation, mandate, opening_msg

    def get_owned_session(self, owner_id: UUID, conversation_id: UUID) -> Conversation:
        for conv in self.db.query(Conversation).all():
            if conv.id == conversation_id:
                if conv.owner_id != owner_id:
                    raise HTTPException(
                        status_code=403,
                        detail={"error": "forbidden", "message": "You do not own this conversation"},
                    )
                return conv
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Conversation not found"},
        )

    def get_mandate_for_session(self, conversation: Conversation) -> Mandate:
        if conversation.mandate_id is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "No mandate linked to this conversation"},
            )
        for mandate in self.db.query(Mandate).all():
            if mandate.id == conversation.mandate_id:
                return mandate
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Mandate not found"},
        )

    def get_messages(self, conversation_id: UUID) -> list[Message]:
        messages = [m for m in self.db.query(Message).all() if m.conversation_id == conversation_id]
        messages.sort(key=lambda item: item.created_at)
        return messages

    # ------------------------------------------------------------------
    # Turn execution
    # ------------------------------------------------------------------

    def run_turn(
        self,
        conversation: Conversation,
        mandate: Mandate,
        owner_id: UUID,
        content: str,
    ) -> tuple[Message, Message, dict, dict, float, list[str], str | None, bool]:
        if conversation.status != "active":
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_error", "message": "Conversation is not active"},
            )

        now = datetime.now(timezone.utc)
        persona_context = self._load_persona_context(owner_id)

        mandate_delta = extract_mandate_delta(content, persona_context)
        apply_delta_to_mandate(mandate, mandate_delta)
        mandate.updated_at = now

        mandate_state = derive_mandate_state(mandate)
        completeness_score = compute_mandate_completeness(mandate_state)
        mandate.completeness_score = completeness_score
        gap_info = analyze_mandate_gaps(mandate_state)
        is_complete = completeness_score >= settings.onboarding_completeness_threshold

        if is_complete:
            agent_text = build_mandate_reflection(mandate_state)
            mandate.is_active = True
            conversation.status = "confirmed"
        else:
            agent_text = gap_info["next_question"] or default_mandate_opening_prompt(persona_context)

        self.db.commit()

        user_msg = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="user",
            content=content,
            mandate_delta=mandate_delta or None,
            completeness_after=completeness_score,
            gaps_remaining=gap_info["gaps_remaining"],
            created_at=now,
            token_count=None,
        )
        agent_msg = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="agent",
            content=agent_text,
            mandate_delta=None,
            completeness_after=completeness_score,
            gaps_remaining=gap_info["gaps_remaining"],
            created_at=now,
            token_count=None,
        )

        self.db.add(user_msg)
        self.db.add(agent_msg)
        conversation.last_message_at = now
        self.db.commit()
        self.db.refresh(user_msg)
        self.db.refresh(agent_msg)

        return (
            user_msg,
            agent_msg,
            mandate_state,
            mandate_delta,
            completeness_score,
            gap_info["gaps_remaining"],
            gap_info["next_gap"],
            is_complete,
        )
