"""
Conversation extraction helpers.

Phase 1 implementation uses deterministic parsing so onboarding can be tested
without live LLM dependencies.
"""
from __future__ import annotations

import re
from typing import Any


_CATEGORY_KEYWORDS = {
    "furniture": {"sofa", "couch", "table", "desk", "chair", "dresser", "bed"},
    "car": {"car", "sedan", "suv", "truck"},
    "appliance": {"fridge", "refrigerator", "washer", "dryer", "stove", "microwave"},
    "electronics": {"laptop", "phone", "tv", "television", "monitor"},
}

_STYLE_TERMS = [
    "mid-century",
    "modern",
    "minimalist",
    "industrial",
    "bohemian",
    "traditional",
    "rustic",
]

_CONDITION_TERMS = ["new", "like new", "excellent", "good", "fair", "used"]


def _find_budget(text: str) -> dict[str, float]:
    lowered = text.lower()
    range_match = re.search(
        r"(?:\$?\s*(\d{2,6}))\s*(?:-|to|and)\s*\$?\s*(\d{2,6})",
        lowered,
    )
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        return {"min": min(low, high), "max": max(low, high)}

    max_match = re.search(r"(?:under|below|less than|max(?:imum)?)\s*\$?\s*(\d{2,6})", lowered)
    if max_match:
        return {"max": float(max_match.group(1))}

    min_match = re.search(r"(?:at least|minimum|min)\s*\$?\s*(\d{2,6})", lowered)
    if min_match:
        return {"min": float(min_match.group(1))}

    return {}


def _find_location(text: str) -> str | None:
    match = re.search(r"\bin\s+([a-zA-Z][a-zA-Z\s]{1,40})", text)
    if not match:
        return None
    candidate = match.group(1).strip(" .,!?")
    candidate = re.split(r"\b(between|under|within|with|around|by)\b", candidate, maxsplit=1, flags=re.IGNORECASE)[
        0
    ].strip()
    return candidate or None


def _find_timing(text: str) -> str | None:
    lowered = text.lower()
    if "asap" in lowered:
        return "asap"
    within_match = re.search(r"within\s+([a-z0-9\s-]{1,24})", lowered)
    if within_match:
        return within_match.group(1).strip(" .,!?")
    by_match = re.search(r"\bby\s+([a-z0-9\s-]{1,24})", lowered)
    if by_match:
        return f"by {by_match.group(1).strip(' .,!?')}"
    return None


def _find_condition(text: str) -> str | None:
    lowered = text.lower()
    for term in _CONDITION_TERMS:
        if term in lowered:
            return term
    return None


def _find_style_preferences(text: str) -> list[str]:
    lowered = text.lower()
    return [term for term in _STYLE_TERMS if term in lowered]


def _find_dealbreakers(text: str) -> list[str]:
    lowered = text.lower()
    matches = re.findall(r"(?:no|not)\s+([a-zA-Z][a-zA-Z\s-]{1,30})", lowered)
    return [m.strip(" .,!?") for m in matches]


def _infer_intent(text: str) -> str | None:
    lowered = text.lower()
    if "sell" in lowered or "listing my" in lowered:
        return "sell"
    if "offer service" in lowered:
        return "offer_service"
    if "need service" in lowered or "looking for a service" in lowered:
        return "request_service"
    if any(token in lowered for token in ["buy", "looking for", "need", "want"]):
        return "buy"
    return None


def _infer_vertical(intent_type: str | None) -> str | None:
    if intent_type in {"request_service", "offer_service"}:
        return "services"
    if intent_type in {"buy", "sell", "discover"}:
        return "goods"
    return None


def _infer_category(text: str) -> str | None:
    lowered = text.lower()
    for category, tokens in _CATEGORY_KEYWORDS.items():
        if any(token in lowered for token in tokens):
            return category
    return None


def _to_mandate_delta(persona_delta: dict[str, Any]) -> dict[str, Any]:
    delta: dict[str, Any] = {}
    if "intent_type" in persona_delta:
        delta["intent_type"] = persona_delta["intent_type"]
    if "vertical" in persona_delta:
        delta["vertical"] = persona_delta["vertical"]
    if "category" in persona_delta:
        delta["category"] = persona_delta["category"]

    budget = persona_delta.get("budget")
    if isinstance(budget, dict) and budget:
        delta["negotiation_range"] = [{"dimension": "price", **budget}]

    hard_constraints: list[dict[str, Any]] = []
    if persona_delta.get("location"):
        hard_constraints.append({"field": "location", "value": persona_delta["location"]})
    if persona_delta.get("condition"):
        hard_constraints.append({"field": "condition", "value": persona_delta["condition"]})
    if persona_delta.get("timing"):
        hard_constraints.append({"field": "timing", "value": persona_delta["timing"]})
    if hard_constraints:
        delta["hard_constraints"] = hard_constraints

    if persona_delta.get("style_preferences"):
        delta["soft_preferences"] = [
            {"field": "style", "value": value} for value in persona_delta["style_preferences"]
        ]
    if persona_delta.get("dealbreakers"):
        delta["dealbreakers"] = list(persona_delta["dealbreakers"])
    return delta


def extract_persona_and_mandate_delta(
    user_message: str,
    current_persona: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    _ = current_persona or {}
    persona_delta: dict[str, Any] = {}

    intent_type = _infer_intent(user_message)
    if intent_type:
        persona_delta["intent_type"] = intent_type
        vertical = _infer_vertical(intent_type)
        if vertical:
            persona_delta["vertical"] = vertical

    category = _infer_category(user_message)
    if category:
        persona_delta["category"] = category

    budget = _find_budget(user_message)
    if budget:
        persona_delta["budget"] = budget

    location = _find_location(user_message)
    if location:
        persona_delta["location"] = location

    condition = _find_condition(user_message)
    if condition:
        persona_delta["condition"] = condition

    timing = _find_timing(user_message)
    if timing:
        persona_delta["timing"] = timing

    styles = _find_style_preferences(user_message)
    if styles:
        persona_delta["style_preferences"] = styles

    dealbreakers = _find_dealbreakers(user_message)
    if dealbreakers:
        persona_delta["dealbreakers"] = dealbreakers

    return persona_delta, _to_mandate_delta(persona_delta)
