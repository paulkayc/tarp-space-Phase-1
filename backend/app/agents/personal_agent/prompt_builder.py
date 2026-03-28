from __future__ import annotations

from typing import Any


def default_opening_prompt() -> str:
    return (
        "Hi, I'm your Personal Agent. I'd love to get to know you a bit — "
        "starting with your name and where you're based."
    )


def build_memory_reflection(persona: dict[str, Any]) -> str:
    """Return a plain-text summary of what the personal agent knows about the user."""
    if not persona:
        return (
            "I don't have any saved details from memory yet. "
            "Tell me your name and where you're based to get started."
        )

    parts: list[str] = []

    name = persona.get("name")
    if name:
        parts.append(f"your name: {name}")

    home_city = persona.get("home_city")
    if home_city:
        parts.append(f"home city: {home_city}")

    comm_style = persona.get("communication_style")
    if comm_style:
        parts.append(f"communication style: {comm_style}")

    interests = persona.get("general_interests")
    if interests:
        if isinstance(interests, list):
            parts.append(f"interests: {', '.join(interests)}")
        else:
            parts.append(f"interests: {interests}")

    deal_sens = persona.get("deal_sensitivity")
    if deal_sens:
        parts.append(f"deal priority: {deal_sens}")

    summary = "; ".join(parts) if parts else "a few early details"
    return f"Here's what I remember from memory: {summary}."
