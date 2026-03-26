"""
Plain-language reflection used when onboarding completeness threshold is reached.
"""
from __future__ import annotations

from typing import Any


def build_reflection(persona: dict[str, Any]) -> str:
    intent = persona.get("intent_type", "find")
    category = persona.get("category", "item")
    location = persona.get("location", "your preferred area")
    budget = persona.get("budget", {})
    condition = persona.get("condition", "any condition")
    timing = persona.get("timing", "flexible timing")
    styles = persona.get("style_preferences", [])
    dealbreakers = persona.get("dealbreakers", [])

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
