"""
Mandate-specific extraction helpers.

Wraps extract_mandate_delta from the shared conversation extractor and
exposes it as the canonical extraction function for the Mandate Agent.
"""
from __future__ import annotations

from typing import Any

from app.services.conversation.extractor import extract_mandate_delta as _extract_mandate_delta


def extract_mandate_delta(
    user_message: str,
    persona_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Extract mandate fields from a user message.

    persona_context may include 'home_city' which is used as a location
    fallback when no explicit location is mentioned.
    """
    return _extract_mandate_delta(user_message, persona_context)
