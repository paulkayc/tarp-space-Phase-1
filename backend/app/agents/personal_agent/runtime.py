from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.agents.personal_agent.memory.service import PersonalMemoryService
from app.agents.personal_agent.pipeline import Pipeline, append_action_log, enforce_one_question
from app.agents.personal_agent.policy import is_memory_question
from app.agents.personal_agent.prompt_builder import build_memory_reflection, default_opening_prompt
from app.agents.personal_agent.tools import ToolExecutor, ToolRegistry, register_builtin_tools
from app.core.config import settings
from app.db.models import OnboardingMessage, OnboardingSession, User
from app.observability.events import emit_personal_agent_turn_event
from app.services.conversation.extractor import extract_persona_delta
from app.services.conversation.gap_analyzer import analyze_persona_gaps, compute_persona_completeness
from app.services.conversation.reflector import build_persona_reflection
from app.services.llm.client import LLMCallError, get_llm_client
from app.services.llm.prompts.personal_agent import RESPONSE_SYSTEM_PROMPT


class PersonalAgentRuntime:
    def __init__(self, db: Session):
        self.db = db
        self.memory_service = PersonalMemoryService(db)
        self.tool_registry = ToolRegistry()
        register_builtin_tools(self.tool_registry, self.memory_service)
        self.tool_executor = ToolExecutor(self.tool_registry)
        self.pipeline = Pipeline()
        self.pipeline.add_step(append_action_log)

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
        session = self.db.query(OnboardingSession).filter_by(id=conversation_id).first()
        if session is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": "Conversation not found"})
        if session.owner_id != owner_id:
            raise HTTPException(
                status_code=403,
                detail={"error": "forbidden", "message": "You do not own this conversation"},
            )
        return session

    def get_messages(self, session_id: UUID) -> list[OnboardingMessage]:
        messages = self.db.query(OnboardingMessage).filter_by(session_id=session_id).all()
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

    def _generate_agent_response(
        self,
        session_id: UUID,
        user_message: str,
        persona_delta: dict,
        gap_info: dict,
        is_complete: bool,
        merged_persona: dict,
    ) -> tuple[str, int]:
        """Call LLM for a natural language response. Returns (text, total_tokens).

        Falls back to the template gap question if the LLM is unavailable.
        """
        try:
            client = get_llm_client()

            # Build conversation history (last N turns, oldest first)
            history = self.get_messages(session_id)
            history = history[-(settings.llm_max_history_turns * 2):]

            messages = []
            for msg in history:
                role = "assistant" if msg.role == "agent" else "user"
                messages.append({"role": role, "content": msg.content})
            messages.append({"role": "user", "content": user_message})

            # Inject extraction context and next-gap hint into system prompt
            context_lines = [RESPONSE_SYSTEM_PROMPT]
            if persona_delta:
                context_lines.append(f"\nJust extracted from this message: {persona_delta}")
            if is_complete:
                context_lines.append("\nThe user's profile is now complete.")
            elif gap_info.get("next_gap"):
                context_lines.append(
                    f"\nNext field to collect: {gap_info['next_gap']}. "
                    f"Suggested question: {gap_info.get('next_question', '')}"
                )
            system = "\n".join(context_lines)

            response = client.messages.create(
                model=settings.llm_model,
                max_tokens=settings.llm_max_tokens,
                system=system,
                messages=messages,
            )
            text = ""
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    text = block.text
                    break
            total_tokens = (
                getattr(response.usage, "input_tokens", 0)
                + getattr(response.usage, "output_tokens", 0)
            )
            return text or (gap_info.get("next_question") or default_opening_prompt()), total_tokens
        except (LLMCallError, Exception):
            fallback = gap_info.get("next_question") or default_opening_prompt()
            return fallback, 0

    def run_turn(
        self,
        session: OnboardingSession,
        owner: User,
        content: str,
    ) -> tuple[OnboardingMessage, OnboardingMessage, dict, dict, float, list[str], str | None, bool]:
        emit_personal_agent_turn_event(
            owner_id=str(owner.id),
            conversation_id=str(session.id),
            status="started",
        )
        if session.status != "active":
            raise HTTPException(
                status_code=422,
                detail={"error": "validation_error", "message": "Conversation is not active"},
            )

        now = datetime.now(timezone.utc)
        existing_persona = owner.persona or {}

        if is_memory_question(content):
            persona_delta = {}
            merged_persona = existing_persona
            completeness_score = compute_persona_completeness(merged_persona)
            gap_info = analyze_persona_gaps(merged_persona)
            memory_hits = self.tool_executor.execute(
                "memory_search", owner_id=owner.id, query="preferences", limit=5
            )
            if memory_hits:
                rendered = "; ".join([item.content for item in memory_hits])
                agent_text = f"Here's what I remember from memory: {rendered}."
            else:
                agent_text = build_memory_reflection(merged_persona)
            is_complete = completeness_score >= settings.onboarding_completeness_threshold
            response_tokens = 0
        else:
            persona_delta = extract_persona_delta(content, existing_persona)
            merged_persona = self._merge_persona(existing_persona, persona_delta)
            owner.persona = merged_persona
            self._persist_persona_memories(owner.id, persona_delta)
            completeness_score = compute_persona_completeness(merged_persona)
            gap_info = analyze_persona_gaps(merged_persona)
            is_complete = completeness_score >= settings.onboarding_completeness_threshold

            if is_complete:
                agent_text = build_persona_reflection(merged_persona)
                owner.onboarding_completed_at = now
                response_tokens = 0
            else:
                agent_text, response_tokens = self._generate_agent_response(
                    session_id=session.id,
                    user_message=content,
                    persona_delta=persona_delta,
                    gap_info=gap_info,
                    is_complete=is_complete,
                    merged_persona=merged_persona,
                )

        agent_text = enforce_one_question(agent_text)
        self.pipeline.run({"action_message": "turn_processed"})

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
            persona_delta=None,
            completeness_after=completeness_score,
            token_count=response_tokens or None,
            created_at=now,
        )

        self.db.add(user_msg)
        self.db.add(agent_msg)
        session.last_message_at = now
        self.db.commit()
        self.db.refresh(user_msg)
        self.db.refresh(agent_msg)
        emit_personal_agent_turn_event(
            owner_id=str(owner.id),
            conversation_id=str(session.id),
            status="completed",
        )

        return (
            user_msg,
            agent_msg,
            merged_persona,
            persona_delta,
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
            self.tool_executor.execute(
                "memory_add",
                owner_id=owner_id,
                content=content,
                tags=[key, "persona", "preferences"],
                source="inferred",
                confidence=0.8,
            )

    def list_tools(self) -> list[dict[str, str]]:
        return self.tool_registry.list()
