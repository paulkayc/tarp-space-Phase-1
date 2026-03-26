"""
Mandate helper functions used by API routes.
"""
from __future__ import annotations

from typing import Any

from app.db.models import Mandate, User


def _append_unique(existing: list[Any], new_items: list[Any]) -> list[Any]:
    result = list(existing)
    for item in new_items:
        if item not in result:
            result.append(item)
    return result


def prefill_mandate_from_persona(mandate: Mandate, owner: User) -> None:
    persona = owner.persona or {}
    if not isinstance(persona, dict):
        return

    if mandate.intent_type is None and persona.get("intent_type"):
        mandate.intent_type = persona["intent_type"]
    if mandate.vertical is None and persona.get("vertical"):
        mandate.vertical = persona["vertical"]
    if mandate.category is None and persona.get("category"):
        mandate.category = persona["category"]

    budget = persona.get("budget")
    if isinstance(budget, dict) and (budget.get("min") is not None or budget.get("max") is not None):
        if not isinstance(mandate.negotiation_range, list):
            mandate.negotiation_range = []
        price_entry = {"dimension": "price"}
        if budget.get("min") is not None:
            price_entry["min"] = budget["min"]
        if budget.get("max") is not None:
            price_entry["max"] = budget["max"]
        if price_entry not in mandate.negotiation_range:
            mandate.negotiation_range = [price_entry, *mandate.negotiation_range]

    if not isinstance(mandate.hard_constraints, list):
        mandate.hard_constraints = []
    for field_name in ["location", "condition", "timing"]:
        if persona.get(field_name):
            entry = {"field": field_name, "value": persona[field_name]}
            if entry not in mandate.hard_constraints:
                mandate.hard_constraints.append(entry)

    if not isinstance(mandate.soft_preferences, list):
        mandate.soft_preferences = []
    styles = persona.get("style_preferences")
    if isinstance(styles, list) and styles:
        mapped_styles = [{"field": "style", "value": style} for style in styles if isinstance(style, str)]
        mandate.soft_preferences = _append_unique(mandate.soft_preferences, mapped_styles)

    if not isinstance(mandate.dealbreakers, list):
        mandate.dealbreakers = []
    dealbreakers = persona.get("dealbreakers")
    if isinstance(dealbreakers, list) and dealbreakers:
        mandate.dealbreakers = _append_unique(mandate.dealbreakers, [d for d in dealbreakers if isinstance(d, str)])
