"""
Conversation extraction helpers.

Public API:
  extract_persona_delta()   — used by the Personal Agent runtime
  extract_mandate_delta()   — used by the Mandate Agent runtime and /conversations

Both functions call the LLM (tool_use) for structured extraction.  On failure
they raise so the calling runtime can handle the error gracefully and surface a
human-readable message in the chat rather than returning a 500.
"""
from __future__ import annotations

import time
from typing import Any

import structlog

from app.core.config import settings
from app.services.llm.client import LLMCallError, get_llm_client
from app.services.llm.prompts.mandate_agent import (
    EXTRACTION_SYSTEM_PROMPT as _MANDATE_EXTRACTION_PROMPT,
)
from app.services.llm.prompts.personal_agent import (
    EXTRACTION_SYSTEM_PROMPT as _PERSONA_EXTRACTION_PROMPT,
)
from app.services.llm.schemas import MANDATE_EXTRACTION_TOOL, PERSONA_EXTRACTION_TOOL

logger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _infer_vertical(intent_type: str | None) -> str | None:
    if intent_type in {"request_service", "offer_service"}:
        return "services"
    if intent_type in {"buy", "sell", "discover"}:
        return "goods"
    return None


# ---------------------------------------------------------------------------
# LLM extraction — Persona
# ---------------------------------------------------------------------------

def _llm_extract_persona(user_message: str, client: Any) -> dict[str, Any]:
    """Call LLM to extract persona fields.  Raises on any failure."""
    log = logger.bind(agent="personal", model=settings.llm_model)
    log.info("llm_extraction_call_started", message_len=len(user_message))

    t0 = time.perf_counter()
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=256,
        system=_PERSONA_EXTRACTION_PROMPT,
        tools=[PERSONA_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_persona_fields"},
        messages=[{"role": "user", "content": user_message}],
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    log.info(
        "llm_extraction_call_complete",
        elapsed_ms=elapsed_ms,
        stop_reason=response.stop_reason,
        input_tokens=getattr(response.usage, "input_tokens", None),
        output_tokens=getattr(response.usage, "output_tokens", None),
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

            log.info(
                "llm_extraction_parsed",
                fields_extracted=list(delta.keys()),
                field_count=len(delta),
            )
            return delta

    log.warning("llm_extraction_no_tool_block", stop_reason=response.stop_reason)
    return {}


# ---------------------------------------------------------------------------
# LLM extraction — Mandate
# ---------------------------------------------------------------------------

def _llm_extract_mandate(
    user_message: str,
    persona_context: dict[str, Any],
    client: Any,
) -> dict[str, Any]:
    """Call LLM to extract mandate fields.  Raises on any failure."""
    log = logger.bind(agent="mandate", model=settings.llm_model)
    log.info("llm_extraction_call_started", message_len=len(user_message))

    t0 = time.perf_counter()
    response = client.messages.create(
        model=settings.llm_model,
        max_tokens=512,
        system=_MANDATE_EXTRACTION_PROMPT,
        tools=[MANDATE_EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "extract_mandate_fields"},
        messages=[{"role": "user", "content": user_message}],
    )
    elapsed_ms = round((time.perf_counter() - t0) * 1000)

    log.info(
        "llm_extraction_call_complete",
        elapsed_ms=elapsed_ms,
        stop_reason=response.stop_reason,
        input_tokens=getattr(response.usage, "input_tokens", None),
        output_tokens=getattr(response.usage, "output_tokens", None),
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

            log.info(
                "llm_extraction_parsed",
                fields_extracted=list(delta.keys()),
                field_count=len(delta),
            )
            return delta

    log.warning("llm_extraction_no_tool_block", stop_reason=response.stop_reason)
    return {}


# ---------------------------------------------------------------------------
# Public extraction functions
# ---------------------------------------------------------------------------

def extract_persona_delta(
    user_message: str,
    current_persona: dict[str, Any] | None = None,
    _client: Any = None,
) -> dict[str, Any]:
    """Extract personal profile fields from a user message via LLM tool_use.

    Raises LLMCallError (or the underlying anthropic exception) on failure so
    the runtime can catch it and surface a user-facing error message.
    """
    log = logger.bind(agent="personal")
    log.info("extract_persona_delta_started", message_len=len(user_message))

    try:
        client = _client if _client is not None else get_llm_client()
        delta = _llm_extract_persona(user_message, client)
        log.info("extract_persona_delta_complete", delta_keys=list(delta.keys()))
        return delta
    except LLMCallError:
        log.error("extract_persona_delta_failed_llm_config")
        raise
    except Exception as exc:
        log.error(
            "extract_persona_delta_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise


def extract_mandate_delta(
    user_message: str,
    persona_context: dict[str, Any] | None = None,
    _client: Any = None,
) -> dict[str, Any]:
    """Extract mandate fields from a user message via LLM tool_use.

    persona_context may include 'home_city' used as a location fallback.
    Raises on failure so the runtime can catch and handle gracefully.
    """
    persona_context = persona_context or {}
    log = logger.bind(agent="mandate")
    log.info("extract_mandate_delta_started", message_len=len(user_message))

    try:
        client = _client if _client is not None else get_llm_client()
        delta = _llm_extract_mandate(user_message, persona_context, client)
        log.info("extract_mandate_delta_complete", delta_keys=list(delta.keys()))
        return delta
    except LLMCallError:
        log.error("extract_mandate_delta_failed_llm_config")
        raise
    except Exception as exc:
        log.error(
            "extract_mandate_delta_failed",
            error_type=type(exc).__name__,
            error=str(exc),
        )
        raise
