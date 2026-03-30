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


# ---------------------------------------------------------------------------
# Matching / Search events
# ---------------------------------------------------------------------------

def emit_search_started(mandate_id: str, mandate_version: int, search_id: str) -> dict[str, Any]:
    return emit_event(
        "search_started",
        mandate_id=mandate_id,
        mandate_version=mandate_version,
        search_id=search_id,
    )


def emit_privacy_gate_decision(
    mandate_id: str,
    field: str,
    action: str,
    rule_applied: str,
) -> dict[str, Any]:
    return emit_event(
        "privacy_gate_decision",
        mandate_id=mandate_id,
        field=field,
        action=action,
        rule_applied=rule_applied,
    )


def emit_search_completed(
    search_id: str,
    mandate_id: str,
    candidate_count_pre_filter: int,
    candidate_count_post_filter: int,
    top_score: float,
    latency_ms: int,
) -> dict[str, Any]:
    return emit_event(
        "search_completed",
        search_id=search_id,
        mandate_id=mandate_id,
        candidate_count_pre_filter=candidate_count_pre_filter,
        candidate_count_post_filter=candidate_count_post_filter,
        top_score=top_score,
        latency_ms=latency_ms,
    )


def emit_escalation_triggered(
    search_id: str,
    result_id: str,
    listing_id: str,
    threshold_delta: float,
    question_text: str,
) -> dict[str, Any]:
    return emit_event(
        "escalation_triggered",
        search_id=search_id,
        result_id=result_id,
        listing_id=listing_id,
        threshold_delta=threshold_delta,
        question_text=question_text,
    )


def emit_signal_received(
    owner_id: str,
    search_result_id: str,
    signal_type: str,
    reason: str | None,
    mandate_delta_applied: dict[str, Any] | None,
) -> dict[str, Any]:
    return emit_event(
        "signal_received",
        owner_id=owner_id,
        search_result_id=search_result_id,
        signal_type=signal_type,
        reason=reason,
        mandate_delta_applied=mandate_delta_applied or {},
    )


def emit_mandate_refined(
    mandate_id: str,
    field_changed: str,
    trigger_signal_id: str,
    old_value: Any,
    new_value: Any,
) -> dict[str, Any]:
    return emit_event(
        "mandate_refined",
        mandate_id=mandate_id,
        field_changed=field_changed,
        trigger_signal_id=trigger_signal_id,
        old_value=old_value,
        new_value=new_value,
    )
