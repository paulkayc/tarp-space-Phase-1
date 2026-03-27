"""Structured event logging helpers for agent flows."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog

logger = structlog.get_logger(__name__)


def emit_event(event: str, **payload: Any) -> dict[str, Any]:
    record = {
        "event": event,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **payload,
    }
    log_payload = dict(record)
    log_payload["event_name"] = log_payload.pop("event")
    logger.info("structured_event", **log_payload)
    return record


def emit_personal_agent_turn_event(owner_id: str, conversation_id: str, status: str) -> dict[str, Any]:
    return emit_event(
        "personal_agent_turn",
        owner_id=owner_id,
        conversation_id=conversation_id,
        status=status,
    )


def emit_memory_event(owner_id: str, memory_id: str, action: str) -> dict[str, Any]:
    return emit_event(
        "personal_memory_event",
        owner_id=owner_id,
        memory_id=memory_id,
        action=action,
    )


def emit_tool_event(owner_id: str, tool_name: str, status: str) -> dict[str, Any]:
    return emit_event(
        "personal_agent_tool_event",
        owner_id=owner_id,
        tool_name=tool_name,
        status=status,
    )
