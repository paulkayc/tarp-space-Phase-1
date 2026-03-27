from __future__ import annotations

from typing import Any


def build_persona_reflection(persona: dict[str, Any]) -> str:
    name = persona.get("preferred_name") or "(name not set)"
    area = persona.get("city_or_area") or "(area not set)"
    communication = persona.get("communication_style") or "(communication style not set)"
    styles = persona.get("style_preferences") or []
    constraints = persona.get("personal_constraints") or []

    styles_text = ", ".join(styles) if styles else "none yet"
    constraints_text = ", ".join(constraints) if constraints else "none yet"

    return (
        f"Here is what I know about you so far: name {name}, area {area}, "
        f"communication style {communication}, style preferences {styles_text}, "
        f"and personal constraints {constraints_text}. Did I capture this correctly?"
    )
