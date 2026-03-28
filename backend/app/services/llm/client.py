"""
Anthropic SDK wrapper.

All LLM calls in this codebase go through this module.
Provides a thin factory and a typed error for upstream handling.
"""
from __future__ import annotations

import anthropic

from app.core.config import settings


class LLMCallError(Exception):
    """Raised when an LLM call fails after all retries."""


def get_llm_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client.

    The SDK retries 429 and 5xx responses automatically (default max_retries=2
    with exponential backoff).  Raises LLMCallError if the API key is missing.
    """
    if not settings.anthropic_api_key:
        raise LLMCallError("ANTHROPIC_API_KEY is not configured")
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)
