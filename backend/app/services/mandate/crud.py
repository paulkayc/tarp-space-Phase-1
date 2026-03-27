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
    """Pre-populate mandate defaults from the user's personal profile.

    The Personal Agent stores WHO the user is (name, home_city, communication
    style, etc.).  The Mandate Agent owns WHAT the user wants right now
    (intent, category, budget, etc.).

    The only durable cross-agent mapping is:
      home_city → default location constraint (if no location already set)
    """
    persona = owner.persona or {}
    if not isinstance(persona, dict):
        return

    home_city = persona.get("home_city")
    if home_city and isinstance(home_city, str) and home_city.strip():
        if not isinstance(mandate.hard_constraints, list):
            mandate.hard_constraints = []
        already_has_location = any(
            isinstance(c, dict) and c.get("field") == "location"
            for c in mandate.hard_constraints
        )
        if not already_has_location:
            mandate.hard_constraints.append({"field": "location", "value": home_city.strip()})
