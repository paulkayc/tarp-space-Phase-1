from __future__ import annotations

from typing import Any


def default_opening_prompt() -> str:
    return "Hi, I am your Personal Agent. Tell me what matters to you so I can remember it and help better over time."


def build_memory_reflection(persona: dict[str, Any]) -> str:
    if not persona:
        return "I don't have any saved preferences for you yet. Share what you like and I will remember it."

    parts: list[str] = []
    intent = persona.get("intent_type")
    if intent:
        parts.append(f"intent: {intent}")

    category = persona.get("category")
    if category:
        parts.append(f"category: {category}")

    location = persona.get("location")
    if location:
        parts.append(f"location: {location}")

    budget = persona.get("budget")
    if isinstance(budget, dict) and budget:
        parts.append(f"budget: {budget}")

    styles = persona.get("style_preferences")
    if styles:
        parts.append(f"styles: {styles}")

    dealbreakers = persona.get("dealbreakers")
    if dealbreakers:
        parts.append(f"dealbreakers: {dealbreakers}")

    summary = "; ".join(parts) if parts else "a few early onboarding details"
    return f"Here's what I currently remember: {summary}."
