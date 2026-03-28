"""
Mandate Agent runtime.

Owns a specific user request (buy/sell/service) and iterates through mandate
gap questions until the mandate is complete.  Uses the existing Conversation
and Message DB models.  Reads persona memory (read-only) to pre-populate
defaults such as home_city → location.
"""
from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

import structlog
from fastapi import HTTPException
from sqlalchemy.orm import Session

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
from app.services.conversation.extractor import extract_mandate_delta
from app.services.llm.client import LLMCallError, get_llm_client
from app.services.llm.prompts.mandate_agent import RESPONSE_SYSTEM_PROMPT

logger = structlog.get_logger(__name__)

_LLM_ERROR_MESSAGE = (
    "I'm having trouble reaching the AI service right now. "
    "This is usually resolved quickly — please try again in a moment."
)


class MandateAgentRuntime:
    def __init__(self, db: Session):
        self.db = db
        self.memory_service = PersonalMemoryService(db)

    # ------------------------------------------------------------------
    # Persona context
    # ------------------------------------------------------------------

    def _load_persona_context(self, owner_id: UUID) -> dict:
        log = logger.bind(owner_id=str(owner_id))
        log.info("mandate_agent_persona_context_loading")

        memories = self.memory_service.list_memories(owner_id=owner_id)
        context: dict = {}
        _persona_fields = {"name", "home_city", "communication_style", "general_interests", "deal_sensitivity"}
        for memory in memories:
            tags = set(memory.tags or [])
            field = tags & _persona_fields
            if field:
                key = next(iter(field))
                if ":" in memory.content:
                    _, _, raw_value = memory.content.partition(":")
                    context[key] = raw_value.strip()

        log.info(
            "mandate_agent_persona_context_loaded",
            fields_found=list(context.keys()),
            memory_count=len(memories),
        )
        return context

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(
        self,
        owner_id: UUID,
        persona_context: dict | None = None,
    ) -> tuple[Conversation, Mandate, Message]:
        log = logger.bind(owner_id=str(owner_id))
        log.info("mandate_agent_session_creating")

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
        home_city = persona_context.get("home_city")
        if home_city:
            mandate.hard_constraints = [{"field": "location", "value": home_city}]
            log.info("mandate_agent_location_prefilled_from_persona", home_city=home_city)

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
        initial_gaps = list(derive_mandate_state(mandate).keys())
        opening_msg = Message(
            id=uuid4(),
            conversation_id=conversation.id,
            role="agent",
            content=opening_text,
            mandate_delta=None,
            completeness_after=0.0,
            gaps_remaining=initial_gaps,
            created_at=now,
            token_count=None,
        )
        self.db.add(opening_msg)
        self.db.commit()
        self.db.refresh(opening_msg)

        log.info(
            "mandate_agent_session_created",
            conversation_id=str(conversation.id),
            mandate_id=str(mandate.id),
            initial_gaps=initial_gaps,
        )
        return conversation, mandate, opening_msg

    def get_owned_session(self, owner_id: UUID, conversation_id: UUID) -> Conversation:
        conv = self.db.query(Conversation).filter_by(id=conversation_id).first()
        if conv is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Conversation not found"},
            )
        if conv.owner_id != owner_id:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": "You do not own this conversation"},
            )
        return conv

    def get_mandate_for_session(self, conversation: Conversation) -> Mandate:
        if conversation.mandate_id is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "No mandate linked to this conversation"},
            )
        mandate = self.db.query(Mandate).filter_by(id=conversation.mandate_id).first()
        if mandate is None:
            raise HTTPException(
                status_code=404,
                detail={"error": "not_found", "message": "Mandate not found"},
            )
        return mandate

    def get_messages(self, conversation_id: UUID) -> list[Message]:
        messages = self.db.query(Message).filter_by(conversation_id=conversation_id).all()
        messages.sort(key=lambda item: item.created_at)
        return messages

    # ------------------------------------------------------------------
    # LLM response generation (Call 2)
    # ------------------------------------------------------------------

    def _generate_agent_response(
        self,
        conversation_id: UUID,
        user_message: str,
        mandate_delta: dict,
        gap_info: dict,
        is_complete: bool,
        persona_context: dict,
    ) -> tuple[str, int]:
        """Generate a natural language reply.  Raises on failure."""
        log = logger.bind(conversation_id=str(conversation_id))

        history = self.get_messages(conversation_id)
        history_slice = history[-(settings.llm_max_history_turns * 2):]
        log.info(
            "mandate_agent_response_generation_started",
            history_turns=len(history_slice),
            delta_fields=list(mandate_delta.keys()),
            is_complete=is_complete,
            next_gap=gap_info.get("next_gap"),
        )

        client = get_llm_client()

        messages = []
        for msg in history_slice:
            role = "assistant" if msg.role == "agent" else "user"
            messages.append({"role": role, "content": msg.content})
        messages.append({"role": "user", "content": user_message})

        context_lines = [RESPONSE_SYSTEM_PROMPT]
        if mandate_delta:
            context_lines.append(f"\nJust extracted from this message: {mandate_delta}")
        if is_complete:
            context_lines.append("\nThe mandate is now complete.")
        elif gap_info.get("next_gap"):
            context_lines.append(
                f"\nNext field to collect: {gap_info['next_gap']}. "
                f"Suggested question: {gap_info.get('next_question', '')}"
            )
        system = "\n".join(context_lines)

        t0 = time.perf_counter()
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=settings.llm_max_tokens,
            system=system,
            messages=messages,
        )
        elapsed_ms = round((time.perf_counter() - t0) * 1000)

        total_tokens = (
            getattr(response.usage, "input_tokens", 0)
            + getattr(response.usage, "output_tokens", 0)
        )
        text = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                text = block.text
                break

        log.info(
            "mandate_agent_response_generation_complete",
            elapsed_ms=elapsed_ms,
            input_tokens=getattr(response.usage, "input_tokens", None),
            output_tokens=getattr(response.usage, "output_tokens", None),
            total_tokens=total_tokens,
            response_len=len(text),
            stop_reason=response.stop_reason,
        )
        return text or (gap_info.get("next_question") or default_mandate_opening_prompt(persona_context)), total_tokens

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
        turn_start = time.perf_counter()
        log = logger.bind(
            conversation_id=str(conversation.id),
            mandate_id=str(mandate.id),
            owner_id=str(owner_id),
        )
        log.info("mandate_agent_turn_started", message_len=len(content))

        if conversation.status != "active":
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_error", "message": "Conversation is not active"},
            )

        now = datetime.now(timezone.utc)

        # Load persona context every turn (home_city for location fallback)
        persona_context = self._load_persona_context(owner_id)

        # ------------------------------------------------------------------
        # Call 1: Extract mandate delta
        # ------------------------------------------------------------------
        log.info("mandate_agent_extraction_started")
        try:
            t_extract = time.perf_counter()
            mandate_delta = extract_mandate_delta(content, persona_context)
            extract_ms = round((time.perf_counter() - t_extract) * 1000)
            log.info(
                "mandate_agent_extraction_complete",
                elapsed_ms=extract_ms,
                delta_fields=list(mandate_delta.keys()),
                delta_field_count=len(mandate_delta),
            )
        except Exception as exc:
            log.error(
                "mandate_agent_extraction_failed",
                error_type=type(exc).__name__,
                error=str(exc),
            )
            mandate_state = derive_mandate_state(mandate)
            completeness_score = float(mandate.completeness_score or 0.0)
            gap_info = analyze_mandate_gaps(mandate_state)
            return self._persist_turn(
                conversation=conversation,
                content=content,
                agent_text=_LLM_ERROR_MESSAGE,
                mandate_delta={},
                mandate_state=mandate_state,
                completeness_score=completeness_score,
                gap_info=gap_info,
                is_complete=False,
                response_tokens=0,
                now=now,
                turn_start=turn_start,
                log=log,
            )

        # Apply delta to mandate ORM object
        apply_delta_to_mandate(mandate, mandate_delta)
        mandate.updated_at = now

        mandate_state = derive_mandate_state(mandate)
        completeness_score = compute_mandate_completeness(mandate_state)
        mandate.completeness_score = completeness_score
        gap_info = analyze_mandate_gaps(mandate_state)
        is_complete = completeness_score >= settings.onboarding_completeness_threshold

        log.info(
            "mandate_agent_completeness_evaluated",
            completeness_score=round(completeness_score, 3),
            is_complete=is_complete,
            gaps_remaining=gap_info.get("gaps_remaining", []),
            next_gap=gap_info.get("next_gap"),
        )

        # ------------------------------------------------------------------
        # Completion path — no LLM response needed
        # ------------------------------------------------------------------
        if is_complete:
            log.info("mandate_agent_mandate_complete")
            agent_text = build_mandate_reflection(mandate_state)
            mandate.is_active = True
            conversation.status = "confirmed"
            response_tokens = 0
        else:
            # ------------------------------------------------------------------
            # Call 2: Generate natural language response
            # ------------------------------------------------------------------
            try:
                t_response = time.perf_counter()
                agent_text, response_tokens = self._generate_agent_response(
                    conversation_id=conversation.id,
                    user_message=content,
                    mandate_delta=mandate_delta,
                    gap_info=gap_info,
                    is_complete=is_complete,
                    persona_context=persona_context,
                )
                response_ms = round((time.perf_counter() - t_response) * 1000)
                log.info(
                    "mandate_agent_response_generation_succeeded",
                    elapsed_ms=response_ms,
                    tokens=response_tokens,
                )
            except Exception as exc:
                log.error(
                    "mandate_agent_response_generation_failed",
                    error_type=type(exc).__name__,
                    error=str(exc),
                )
                agent_text = _LLM_ERROR_MESSAGE
                response_tokens = 0

        return self._persist_turn(
            conversation=conversation,
            content=content,
            agent_text=agent_text,
            mandate_delta=mandate_delta,
            mandate_state=mandate_state,
            completeness_score=completeness_score,
            gap_info=gap_info,
            is_complete=is_complete,
            response_tokens=response_tokens,
            now=now,
            turn_start=turn_start,
            log=log,
        )

    def _persist_turn(
        self,
        conversation: Conversation,
        content: str,
        agent_text: str,
        mandate_delta: dict,
        mandate_state: dict,
        completeness_score: float,
        gap_info: dict,
        is_complete: bool,
        response_tokens: int,
        now: datetime,
        turn_start: float,
        log: Any,
    ) -> tuple[Message, Message, dict, dict, float, list[str], str | None, bool]:
        log.info("mandate_agent_db_write_started")

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
            token_count=response_tokens or None,
        )

        self.db.add(user_msg)
        self.db.add(agent_msg)
        conversation.last_message_at = now
        self.db.commit()
        self.db.refresh(user_msg)
        self.db.refresh(agent_msg)

        total_ms = round((time.perf_counter() - turn_start) * 1000)
        log.info(
            "mandate_agent_turn_complete",
            user_msg_id=str(user_msg.id),
            agent_msg_id=str(agent_msg.id),
            completeness_score=round(completeness_score, 3),
            is_complete=is_complete,
            gaps_remaining=gap_info.get("gaps_remaining", []),
            response_tokens=response_tokens,
            total_elapsed_ms=total_ms,
        )

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
