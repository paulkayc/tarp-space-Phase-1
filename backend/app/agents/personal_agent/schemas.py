from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PersonalAgentCreateSessionRequest(BaseModel):
    opening_message: str | None = None


class PersonalAgentSendMessageRequest(BaseModel):
    content: str = Field(min_length=1, max_length=4000)


class PersonalAgentMessage(BaseModel):
    id: str
    role: str
    content: str
    persona_delta: dict | None = None
    mandate_delta: dict | None = None
    completeness_after: float = 0.0
    created_at: datetime


class PersonalAgentConversation(BaseModel):
    id: str
    status: str
    created_at: datetime
    last_message_at: datetime
    completed_at: datetime | None = None


class PersonalAgentTurnResult(BaseModel):
    conversation: PersonalAgentConversation
    user_message: PersonalAgentMessage
    agent_message: PersonalAgentMessage
    persona: dict
    persona_delta: dict
    mandate_delta: dict
    completeness_score: float
    gaps_remaining: list[str]
    next_gap: str | None = None
    elicitation_complete: bool
