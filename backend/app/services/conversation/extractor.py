"""
Conversation extraction helpers.

Phase 1 implementation uses deterministic parsing so onboarding can be tested
without live LLM dependencies.

Two independent extraction paths:
  extract_persona_delta()  — used by the Personal Agent (who the user IS)
  extract_mandate_delta()  — used by the Mandate Agent (what the user WANTS)
"""
from __future__ import annotations

import re
from typing import Any


# ---------------------------------------------------------------------------
# Shared keyword tables
# ---------------------------------------------------------------------------

_CATEGORY_KEYWORDS = {
    "furniture": {"sofa", "couch", "table", "desk", "chair", "dresser", "bed", "furniture"},
    "car": {"car", "sedan", "suv", "truck"},
    "appliance": {"fridge", "refrigerator", "washer", "dryer", "stove", "microwave", "appliance", "appliances"},
    "electronics": {"laptop", "phone", "tv", "television", "monitor", "electronics"},
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


# ---------------------------------------------------------------------------
# Persona extraction helpers (Personal Agent path)
# ---------------------------------------------------------------------------

def _find_name(text: str) -> str | None:
    lowered = text.lower()
    patterns = [
        r"my name is ([a-z]+)",
        r"i'm ([a-z]+)",
        r"i am ([a-z]+)",
        r"call me ([a-z]+)",
        r"name'?s ([a-z]+)",
    ]
    # Guard against common false positives
    _stop_words = {
        "a", "an", "the", "not", "just", "here", "there", "going", "looking",
        "trying", "sure", "fine", "good", "bad", "happy", "interested",
    }
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            candidate = match.group(1).strip()
            if candidate not in _stop_words and len(candidate) >= 2:
                return candidate.capitalize()
    return None


def _find_home_city(text: str) -> str | None:
    lowered = text.lower()
    patterns = [
        r"i live in ([a-z][a-z\s]{1,30})",
        r"i'?m based in ([a-z][a-z\s]{1,30})",
        r"i am based in ([a-z][a-z\s]{1,30})",
        r"i'?m from ([a-z][a-z\s]{1,30})",
        r"i am from ([a-z][a-z\s]{1,30})",
        r"based in ([a-z][a-z\s]{1,30})",
        r"located in ([a-z][a-z\s]{1,30})",
    ]
    for pattern in patterns:
        match = re.search(pattern, lowered)
        if match:
            city = match.group(1).strip(" .,!?")
            city = re.split(
                r"\b(and|but|so|where|when|with|the|it)\b",
                city,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if city:
                return city.title()
    return None


def _find_communication_style(text: str) -> str | None:
    lowered = text.lower()
    detailed_tokens = ["full detail", "everything", "detailed", "comprehensive", "thorough", "all the info"]
    brief_tokens = ["quick summary", "brief", "short", "concise", "just the highlights", "quick"]
    for token in detailed_tokens:
        if token in lowered:
            return "detailed"
    for token in brief_tokens:
        if token in lowered:
            return "brief"
    return None


def _find_general_interests(text: str) -> list[str]:
    lowered = text.lower()
    interests = []
    for category, tokens in _CATEGORY_KEYWORDS.items():
        if any(token in lowered for token in tokens):
            interests.append(category)
    return interests


def _find_deal_sensitivity(text: str) -> str | None:
    lowered = text.lower()
    price_tokens = ["best price", "cheapest", "lowest price", "bargain", "affordable", "save money", "price matters", "price-sensitive"]
    quality_tokens = ["best quality", "high quality", "premium", "top quality", "quality matters", "well-made", "durable"]
    convenience_tokens = ["fastest", "most convenient", "convenience", "quick delivery", "near me", "close by"]
    for token in price_tokens:
        if token in lowered:
            return "price_first"
    for token in quality_tokens:
        if token in lowered:
            return "quality_first"
    for token in convenience_tokens:
        if token in lowered:
            return "convenience_first"
    return None


def extract_persona_delta(
    user_message: str,
    current_persona: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract personal profile fields from a user message.

    Returns only fields that were detected (non-empty).  Existing fields from
    current_persona are NOT included — only the delta from this message.
    """
    _ = current_persona or {}
    delta: dict[str, Any] = {}

    name = _find_name(user_message)
    if name:
        delta["name"] = name

    home_city = _find_home_city(user_message)
    if home_city:
        delta["home_city"] = home_city

    communication_style = _find_communication_style(user_message)
    if communication_style:
        delta["communication_style"] = communication_style

    interests = _find_general_interests(user_message)
    if interests:
        delta["general_interests"] = interests

    deal_sensitivity = _find_deal_sensitivity(user_message)
    if deal_sensitivity:
        delta["deal_sensitivity"] = deal_sensitivity

    return delta


# ---------------------------------------------------------------------------
# Mandate extraction helpers (Mandate Agent path)
# ---------------------------------------------------------------------------

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
    candidate = re.split(
        r"\b(between|under|within|with|around|by)\b",
        candidate,
        maxsplit=1,
        flags=re.IGNORECASE,
    )[0].strip()
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


def extract_mandate_delta(
    user_message: str,
    persona_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract mandate fields from a user message.

    persona_context may include 'home_city' which is used as a location
    fallback when no explicit location is stated in the message.
    """
    persona_context = persona_context or {}
    delta: dict[str, Any] = {}

    intent_type = _infer_intent(user_message)
    if intent_type:
        delta["intent_type"] = intent_type
        vertical = _infer_vertical(intent_type)
        if vertical:
            delta["vertical"] = vertical

    category = _infer_category(user_message)
    if category:
        delta["category"] = category

    budget = _find_budget(user_message)
    if budget:
        delta["negotiation_range"] = [{"dimension": "price", **budget}]

    hard_constraints: list[dict[str, Any]] = []

    location = _find_location(user_message)
    if not location and persona_context.get("home_city"):
        location = persona_context["home_city"]
    if location:
        hard_constraints.append({"field": "location", "value": location})

    condition = _find_condition(user_message)
    if condition:
        hard_constraints.append({"field": "condition", "value": condition})

    timing = _find_timing(user_message)
    if timing:
        hard_constraints.append({"field": "timing", "value": timing})

    if hard_constraints:
        delta["hard_constraints"] = hard_constraints

    styles = _find_style_preferences(user_message)
    if styles:
        delta["soft_preferences"] = [{"field": "style", "value": s} for s in styles]

    dealbreakers = _find_dealbreakers(user_message)
    if dealbreakers:
        delta["dealbreakers"] = dealbreakers

    return delta


# ---------------------------------------------------------------------------
# Legacy combined extractor — kept for the /conversations endpoint.
# New code should call extract_persona_delta or extract_mandate_delta directly.
# ---------------------------------------------------------------------------

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
    """Legacy combined extractor used by /conversations endpoint.

    Extracts mandate-oriented fields (intent, category, budget, etc.) into
    both a 'persona_delta' (stored on user.persona) and a parallel
    'mandate_delta'.  New code should use extract_mandate_delta() directly.
    """
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
