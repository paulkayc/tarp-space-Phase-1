"""
Conversation extraction helpers.

Public API (signatures unchanged):
  extract_persona_delta()         — used by the Personal Agent
  extract_mandate_delta()         — used by the Mandate Agent
  extract_persona_and_mandate_delta() — legacy combined extractor for /conversations

Each public function calls the LLM (structured tool_use extraction) and falls back
to deterministic regex parsing when the LLM is unavailable or returns nothing useful.
"""
from __future__ import annotations

import re
import structlog
from typing import Any

from app.services.llm.client import LLMCallError, get_llm_client
from app.services.llm.schemas import MANDATE_EXTRACTION_TOOL, PERSONA_EXTRACTION_TOOL
from app.services.llm.prompts.personal_agent import EXTRACTION_SYSTEM_PROMPT as _PERSONA_EXTRACTION_PROMPT
from app.services.llm.prompts.mandate_agent import EXTRACTION_SYSTEM_PROMPT as _MANDATE_EXTRACTION_PROMPT
from app.core.config import settings

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Shared keyword tables (used by regex fallback)
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
# Regex fallback helpers — Persona path
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


# ---------------------------------------------------------------------------
# Regex fallback helpers — Mandate path
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


def _find_location_mandate(text: str) -> str | None:
    """Mandate-specific location finder (stricter than generic 'in X' pattern)."""
    lowered = text.lower()
    patterns = [
        r"(?:located?|location|based)\s+in\s+([a-zA-Z][a-zA-Z\s]{1,40})",
        r"(?:deliver(?:ed)?|pick\s*up|available)\s+in\s+([a-zA-Z][a-zA-Z\s]{1,40})",
        r"(?:near|around)\s+([a-zA-Z][a-zA-Z\s]{1,40})",
        r"in\s+((?:[A-Z][a-z]+\s?){1,3})",  # Title-case city names only
    ]
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            candidate = match.group(1).strip(" .,!?")
            candidate = re.split(
                r"\b(between|under|within|with|around|by|and|but)\b",
                candidate,
                maxsplit=1,
                flags=re.IGNORECASE,
            )[0].strip()
            if candidate and len(candidate) >= 3:
                return candidate
    return None


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
    _stop = {"sure", "problem", "idea", "way", "thanks", "thank", "worries"}
    matches = re.findall(r"(?:no|not)\s+([a-zA-Z][a-zA-Z\s-]{1,30})", lowered)
    return [m.strip(" .,!?") for m in matches if m.strip(" .,!?").lower() not in _stop]


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


# ---------------------------------------------------------------------------
# Regex fallback public functions
# ---------------------------------------------------------------------------

def _fallback_extract_persona_delta(
    user_message: str,
    current_persona: dict[str, Any] | None = None,
) -> dict[str, Any]:
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


def _fallback_extract_mandate_delta(
    user_message: str,
    persona_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
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

    location = _find_location_mandate(user_message)
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
# LLM extraction helpers
# ---------------------------------------------------------------------------

def _llm_extract_persona(user_message: str, client: Any) -> dict[str, Any]:
    """Call LLM to extract persona fields. Returns {} on any failure."""
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=256,
        system=_PERSONA_EXTRACTION_PROMPT,
        tools=[PERSONA_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_persona_fields"},
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "extract_persona_fields":
            raw: dict = block.input or {}
            delta: dict[str, Any] = {}
            if raw.get("name"):
                delta["name"] = str(raw["name"])
            if raw.get("home_city"):
                delta["home_city"] = str(raw["home_city"])
            if raw.get("communication_style") in ("detailed", "brief"):
                delta["communication_style"] = raw["communication_style"]
            interests = raw.get("general_interests")
            if isinstance(interests, list) and interests:
                delta["general_interests"] = [str(i) for i in interests]
            if raw.get("deal_sensitivity") in ("price_first", "quality_first", "convenience_first"):
                delta["deal_sensitivity"] = raw["deal_sensitivity"]
            return delta
    return {}


def _llm_extract_mandate(
    user_message: str,
    persona_context: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Call LLM to extract mandate fields. Returns {} on any failure."""
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=512,
        system=_MANDATE_EXTRACTION_PROMPT,
        tools=[MANDATE_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_mandate_fields"},
        messages=[{"role": "user", "content": user_message}],
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use" and block.name == "extract_mandate_fields":
            raw: dict = block.input or {}
            delta: dict[str, Any] = {}

            valid_intents = {"buy", "sell", "request_service", "offer_service"}
            if raw.get("intent_type") in valid_intents:
                delta["intent_type"] = raw["intent_type"]
                vertical = _infer_vertical(raw["intent_type"])
                if raw.get("vertical") in ("goods", "services"):
                    vertical = raw["vertical"]
                if vertical:
                    delta["vertical"] = vertical

            if raw.get("category"):
                delta["category"] = str(raw["category"])

            budget_min = raw.get("budget_min")
            budget_max = raw.get("budget_max")
            if budget_min is not None or budget_max is not None:
                entry: dict[str, Any] = {"dimension": "price"}
                if budget_min is not None:
                    entry["min"] = float(budget_min)
                if budget_max is not None:
                    entry["max"] = float(budget_max)
                delta["negotiation_range"] = [entry]

            hard_constraints: list[dict[str, Any]] = []
            location = raw.get("location") or persona_context.get("home_city")
            if location:
                hard_constraints.append({"field": "location", "value": str(location)})

            valid_conditions = {"new", "like new", "excellent", "good", "fair", "used"}
            if raw.get("condition") in valid_conditions:
                hard_constraints.append({"field": "condition", "value": raw["condition"]})

            if raw.get("timing"):
                hard_constraints.append({"field": "timing", "value": str(raw["timing"])})

            if hard_constraints:
                delta["hard_constraints"] = hard_constraints

            styles = raw.get("style_preferences")
            if isinstance(styles, list) and styles:
                delta["soft_preferences"] = [{"field": "style", "value": str(s)} for s in styles]

            dealbreakers = raw.get("dealbreakers")
            if isinstance(dealbreakers, list) and dealbreakers:
                delta["dealbreakers"] = [str(d) for d in dealbreakers]

            return delta
    return {}


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

def extract_persona_delta(
    user_message: str,
    current_persona: dict[str, Any] | None = None,
    _client: Any = None,
) -> dict[str, Any]:
    """Extract personal profile fields from a user message.

    Attempts LLM extraction first; falls back to regex on any error.
    Returns only the delta (non-empty detected fields).
    """
    try:
        client = _client if _client is not None else get_llm_client()
        return _llm_extract_persona(user_message, client)
    except (LLMCallError, Exception) as exc:
        logger.warning("persona_extraction_llm_failed", error=str(exc), fallback="regex")
        return _fallback_extract_persona_delta(user_message, current_persona)


def extract_mandate_delta(
    user_message: str,
    persona_context: dict[str, Any] | None = None,
    _client: Any = None,
) -> dict[str, Any]:
    """Extract mandate fields from a user message.

    persona_context may include 'home_city' used as a location fallback.
    Attempts LLM extraction first; falls back to regex on any error.
    """
    persona_context = persona_context or {}
    try:
        client = _client if _client is not None else get_llm_client()
        return _llm_extract_mandate(user_message, persona_context, client)
    except (LLMCallError, Exception) as exc:
        logger.warning("mandate_extraction_llm_failed", error=str(exc), fallback="regex")
        return _fallback_extract_mandate_delta(user_message, persona_context)


# ---------------------------------------------------------------------------
# Legacy combined extractor — kept for the /conversations endpoint.
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

    Uses regex only (no LLM) so it has no external dependencies.
    New code should use extract_mandate_delta() directly.
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

    location = _find_location_mandate(user_message)
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
