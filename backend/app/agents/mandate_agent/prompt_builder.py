"""
Prompt helpers for the Mandate Agent.
"""
from __future__ import annotations

from typing import Any


def default_mandate_opening_prompt(persona_context: dict[str, Any] | None = None) -> str:
    """Opening message for a new mandate session.

    If the Personal Agent has already captured the user's name we greet them
    by name; otherwise we use a generic opener.
    """
    name = (persona_context or {}).get("name")
    if name:
        return f"Hi {name}! What are you looking to buy, sell, or get done today?"
    return "What are you looking to buy, sell, or get done today?"


def build_mandate_reflection(mandate_state: dict[str, Any]) -> str:
    """Confirm the mandate fields captured so far."""
    intent = mandate_state.get("intent_type", "find")
    category = mandate_state.get("category", "item")
    location = mandate_state.get("location", "your preferred area")
    budget = mandate_state.get("budget", {})
    condition = mandate_state.get("condition", "any condition")
    timing = mandate_state.get("timing", "flexible timing")
    styles = mandate_state.get("style_preferences", [])
    dealbreakers = mandate_state.get("dealbreakers", [])

    budget_text = "no fixed budget"
    if isinstance(budget, dict):
        if budget.get("min") is not None and budget.get("max") is not None:
            budget_text = f"${int(budget['min'])}-${int(budget['max'])}"
        elif budget.get("max") is not None:
            budget_text = f"up to ${int(budget['max'])}"
        elif budget.get("min") is not None:
            budget_text = f"at least ${int(budget['min'])}"

    style_text = ", ".join(styles) if styles else "no specific style"
    dealbreaker_text = ", ".join(dealbreakers) if dealbreakers else "none noted"

    return (
        f"I've captured that you want to {intent} a {category} near {location}, "
        f"budget {budget_text}, condition {condition}, timing {timing}, "
        f"style preference {style_text}, and dealbreakers: {dealbreaker_text}. "
        "Does this look right?"
    )
