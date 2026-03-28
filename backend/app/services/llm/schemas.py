"""
Tool schemas for LLM-based extraction.

Each schema is passed as the ``tools`` list to ``client.messages.create()``.
``tool_choice={"type": "tool", "name": <name>}`` forces the model to call the
tool, guaranteeing a structured response.
"""
from __future__ import annotations

PERSONA_EXTRACTION_TOOL: dict = {
    "name": "extract_persona_fields",
    "description": (
        "Extract personal profile fields from the user's message. "
        "Only include fields that are explicitly stated or strongly implied. "
        "Return an empty object if nothing relevant is present."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "User's first name.",
            },
            "home_city": {
                "type": "string",
                "description": "City or region where the user lives.",
            },
            "communication_style": {
                "type": "string",
                "enum": ["detailed", "brief"],
                "description": (
                    "'detailed' if the user wants comprehensive information; "
                    "'brief' if they prefer concise summaries."
                ),
            },
            "general_interests": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Marketplace interest areas (e.g. furniture, electronics, cars).",
            },
            "deal_sensitivity": {
                "type": "string",
                "enum": ["price_first", "quality_first", "convenience_first"],
                "description": "What the user prioritises most in transactions.",
            },
        },
        "additionalProperties": False,
    },
}

MANDATE_EXTRACTION_TOOL: dict = {
    "name": "extract_mandate_fields",
    "description": (
        "Extract marketplace transaction intent fields from the user's message. "
        "Only include fields clearly present in the message."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "intent_type": {
                "type": "string",
                "enum": ["buy", "sell", "request_service", "offer_service"],
                "description": "What the user wants to do.",
            },
            "vertical": {
                "type": "string",
                "enum": ["goods", "services"],
                "description": "Marketplace vertical: 'goods' for physical items, 'services' for service requests.",
            },
            "category": {
                "type": "string",
                "description": "Product or service category (e.g. furniture, car, appliance, electronics).",
            },
            "budget_min": {
                "type": "number",
                "description": "Minimum acceptable price.",
            },
            "budget_max": {
                "type": "number",
                "description": "Maximum acceptable price.",
            },
            "location": {
                "type": "string",
                "description": "Geographic location for the transaction.",
            },
            "condition": {
                "type": "string",
                "enum": ["new", "like new", "excellent", "good", "fair", "used"],
                "description": "Required item condition.",
            },
            "timing": {
                "type": "string",
                "description": "Timing requirement (e.g. 'asap', 'within 2 weeks', 'by end of month').",
            },
            "style_preferences": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Aesthetic or style preferences (e.g. modern, minimalist).",
            },
            "dealbreakers": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Things the user will not accept.",
            },
        },
        "additionalProperties": False,
    },
}
