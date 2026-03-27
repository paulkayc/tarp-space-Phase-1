"""
Rule-based gap analysis for personal agent persona collection.

Tracks who the user is (name, city, preferences) — not what they want to buy.
Mandate-specific gap analysis lives in app.agents.mandate_agent.gap_analyzer.
"""
from __future__ import annotations

from typing import Any


_PERSONA_GAP_ORDER = [
    "name",
    "home_city",
    "communication_style",
    "general_interests",
    "deal_sensitivity",
]

_PERSONA_QUESTIONS = {
    "name": "What's your name? I'd like to address you properly.",
    "home_city": "What city do you live in? This helps me find things nearby.",
    "communication_style": "When I share results, do you prefer a quick summary or full detail?",
    "general_interests": "What kinds of things do you usually buy, sell, or look for?",
    "deal_sensitivity": "What matters most to you in a deal — best price, highest quality, or fastest convenience?",
}


def _is_filled(persona: dict[str, Any], key: str) -> bool:
    if key not in persona:
        return False
    value = persona[key]
    if value is None:
        return False
    if isinstance(value, str):
        return value.strip() != ""
    if isinstance(value, (list, dict)):
        return len(value) > 0
    return True


def analyze_persona_gaps(persona: dict[str, Any]) -> dict[str, Any]:
    gaps_remaining = [key for key in _PERSONA_GAP_ORDER if not _is_filled(persona, key)]
    next_gap = gaps_remaining[0] if gaps_remaining else None
    return {
        "gaps_remaining": gaps_remaining,
        "next_gap": next_gap,
        "next_question": _PERSONA_QUESTIONS.get(next_gap) if next_gap else None,
    }


def compute_persona_completeness(persona: dict[str, Any]) -> float:
    """Score 0-1 based on how much personal profile data has been collected.

    Weights:
      name                0.30
      home_city           0.30
      communication_style 0.15
      general_interests   0.15
      deal_sensitivity    0.10

    Threshold 0.70 is reached once name + home_city + one preference field
    are known (e.g. 0.30 + 0.30 + 0.15 = 0.75).
    """
    score = 0.0
    score += 0.30 if _is_filled(persona, "name") else 0.0
    score += 0.30 if _is_filled(persona, "home_city") else 0.0
    score += 0.15 if _is_filled(persona, "communication_style") else 0.0
    score += 0.15 if _is_filled(persona, "general_interests") else 0.0
    score += 0.10 if _is_filled(persona, "deal_sensitivity") else 0.0
    return round(min(score, 1.0), 3)


# ---------------------------------------------------------------------------
# Legacy aliases — kept for the /conversations endpoint until it is retired.
# These resolve to the PERSONA versions; conversations.py should be updated
# to import directly from mandate_agent.gap_analyzer instead.
# ---------------------------------------------------------------------------
analyze_gaps = analyze_persona_gaps
compute_onboarding_completeness = compute_persona_completeness
