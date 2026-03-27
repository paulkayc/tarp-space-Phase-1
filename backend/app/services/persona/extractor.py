from __future__ import annotations

import re
from typing import Any

_STYLE_TERMS = ["modern", "mid-century", "minimalist", "traditional", "industrial"]


def extract_persona_delta(user_message: str, current_persona: dict[str, Any] | None = None) -> dict[str, Any]:
    _ = current_persona or {}
    text = user_message.strip()
    lowered = text.lower()
    delta: dict[str, Any] = {}

    name_match = re.search(r"(?:my name is|i am|call me)\s+([A-Za-z][A-Za-z\s'-]{1,40})", text, re.IGNORECASE)
    if name_match:
        delta["preferred_name"] = name_match.group(1).strip(" .,!?")

    address_match = re.search(r"(?:my address is|i live at)\s+(.{4,120})", text, re.IGNORECASE)
    if address_match:
        delta["address"] = address_match.group(1).strip(" .,!?")

    city_match = re.search(r"(?:i live in|i'm in|im in)\s+([A-Za-z][A-Za-z\s-]{1,40})", text, re.IGNORECASE)
    if city_match:
        delta["city_or_area"] = city_match.group(1).strip(" .,!?")

    if "text me" in lowered or "short messages" in lowered:
        delta["communication_style"] = "concise"
    elif "detailed" in lowered or "explain" in lowered:
        delta["communication_style"] = "detailed"

    styles = [term for term in _STYLE_TERMS if term in lowered]
    if styles:
        delta["style_preferences"] = styles

    constraint_match = re.search(r"(?:please avoid|i can't do|i cannot do)\s+(.{3,80})", lowered)
    if constraint_match:
        delta["personal_constraints"] = [constraint_match.group(1).strip(" .,!?")]

    return delta
