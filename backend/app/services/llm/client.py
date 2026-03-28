"""
Anthropic SDK wrapper.

All LLM calls in this codebase go through this module.
Provides a typed factory and a typed error for upstream handling.
"""
from __future__ import annotations

import structlog
import anthropic

from app.core.config import settings

logger = structlog.get_logger(__name__)


class LLMCallError(Exception):
    """Raised when an LLM call cannot be made (e.g. missing API key)."""


def get_llm_client() -> anthropic.Anthropic:
    """Return a configured Anthropic client.

    The SDK retries 429 and 5xx responses automatically (default max_retries=2
    with exponential backoff).  Raises LLMCallError if the API key is missing.
    """
    api_key_present = bool(settings.anthropic_api_key)
    logger.info(
        "llm_client_requested",
        model=settings.llm_model,
        api_key_present=api_key_present,
        max_tokens=settings.llm_max_tokens,
    )

    if not settings.anthropic_api_key:
        logger.error("llm_client_creation_failed", reason="ANTHROPIC_API_KEY not configured")
        raise LLMCallError("ANTHROPIC_API_KEY is not configured")

    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    logger.info("llm_client_created", model=settings.llm_model)
    return client
