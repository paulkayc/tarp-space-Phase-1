"""
Plain-language reflections for each agent type.

build_persona_reflection()  — Personal Agent completion summary (who the user is)
build_reflection()          — Legacy alias kept for the /conversations endpoint
"""
from __future__ import annotations

from typing import Any


def build_persona_reflection(persona: dict[str, Any]) -> str:
    """Confirm the personal profile captured by the Personal Agent."""
    name = persona.get("name", "there")
    home_city = persona.get("home_city", "your city")
    comm_style = persona.get("communication_style")
    interests = persona.get("general_interests")
    deal_sens = persona.get("deal_sensitivity")

    parts: list[str] = []
    if home_city and home_city != "your city":
        parts.append(f"you're based in {home_city}")
    if comm_style:
        parts.append(f"you prefer {comm_style} updates")
    if interests:
        if isinstance(interests, list):
            parts.append(f"you're generally interested in {', '.join(interests)}")
        else:
            parts.append(f"you're generally interested in {interests}")
    if deal_sens:
        label = {"price_first": "best price", "quality_first": "highest quality", "convenience_first": "fastest convenience"}.get(
            deal_sens, deal_sens
        )
        parts.append(f"you prioritise {label}")

    if parts:
        detail = ", ".join(parts)
        return f"Nice to meet you, {name}! I've noted that {detail}. Does this look right?"
    return f"Nice to meet you, {name}! I'll remember that for future sessions. Does this look right?"


# ---------------------------------------------------------------------------
# Legacy mandate reflection — used by the /conversations endpoint.
# New code should use build_mandate_reflection() from mandate_agent.prompt_builder.
# ---------------------------------------------------------------------------

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
