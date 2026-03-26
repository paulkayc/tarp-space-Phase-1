"""
Onboarding extraction pass — LLM call #1.

Takes a user message + current persona state and returns a partial persona
delta (only newly extractable fields). Tags all extracted fields as
source="inferred". Never asks questions — extraction only.

Token budget: 600 context, 400 output.
"""
import json
import logging

import anthropic

from app.core.config import settings

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a persona extraction assistant for a local marketplace app.

Extract structured information about the user from their message.
Return ONLY the fields you can confidently identify — never infer fields
that are not mentioned. Do not ask questions. Return ONLY valid JSON.

Persona schema targets:
  identity:     { display_name, sex, phone }
  location:     { neighborhood, city, state, zip, coordinates: {lat, lng} }
  preferences:  { style_affinities (array), style_dealbreakers (array),
                  typical_budget_goods: {floor, ceiling},
                  typical_budget_services: {floor, ceiling} }
  lifestyle:    { has_pets (bool), home_type ("apartment"|"house"|"condo"),
                  buying_frequency, selling_frequency }
  trust_seeds:  { community_names (array), willing_to_vouch (bool) }

Rules:
  - Only extract what is explicitly stated or clearly implied.
  - Omit top-level keys that have no extractable fields.
  - Do not re-extract fields that already appear in current_persona.
  - Return {} if nothing can be extracted.
  - Return raw JSON only — no markdown fences, no commentary.\
"""

# Four few-shot examples (user turn + assistant turn pairs)
_FEW_SHOT: list[dict] = [
    {
        "role": "user",
        "content": (
            'Message: "I\'m Alex, I live in Montrose, 77006"\n'
            "current_persona: {}\n\nExtracted:"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "identity": {"display_name": "Alex"},
                "location": {
                    "neighborhood": "Montrose",
                    "zip": "77006",
                    "city": "Houston",
                    "state": "TX",
                },
            }
        ),
    },
    {
        "role": "user",
        "content": (
            'Message: "I have a dog and I rent an apartment near downtown"\n'
            "current_persona: {}\n\nExtracted:"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "lifestyle": {"has_pets": True, "home_type": "apartment"},
                "location": {"neighborhood": "Downtown Houston"},
            }
        ),
    },
    {
        "role": "user",
        "content": (
            'Message: "I love mid-century modern stuff, hate anything ornate or '
            'cheap-looking. Usually spend under $600 on furniture"\n'
            "current_persona: {}\n\nExtracted:"
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "preferences": {
                    "style_affinities": ["mid-century modern"],
                    "style_dealbreakers": ["ornate"],
                    "typical_budget_goods": {"ceiling": 600},
                }
            }
        ),
    },
    {
        "role": "user",
        "content": (
            'Message: "I\'m part of the Heights Neighborhood group and the UH alumni '
            'network"\ncurrent_persona: {}\n\nExtracted:'
        ),
    },
    {
        "role": "assistant",
        "content": json.dumps(
            {
                "trust_seeds": {
                    "community_names": ["Heights Neighborhood", "UH Alumni Network"]
                }
            }
        ),
    },
]


def extract_persona_delta(user_message: str, current_persona: dict) -> dict:
    """
    LLM extraction pass — identifies persona fields from a single user message.

    Returns a partial persona dict with only newly extractable fields.
    Returns {} if nothing can be extracted or the LLM returns invalid JSON.
    """
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)

    messages = _FEW_SHOT + [
        {
            "role": "user",
            "content": (
                f'Message: "{user_message}"\n'
                f"current_persona: {json.dumps(current_persona)}\n\n"
                "Extracted:"
            ),
        }
    ]

    try:
        response = client.messages.create(
            model=settings.llm_model,
            max_tokens=400,
            system=_SYSTEM_PROMPT,
            messages=messages,
        )
        raw = response.content[0].text.strip()
        delta = json.loads(raw)
        if not isinstance(delta, dict):
            return {}
        return delta
    except (json.JSONDecodeError, Exception) as exc:
        logger.warning("persona_extraction_failed", extra={"error": str(exc)})
        return {}
