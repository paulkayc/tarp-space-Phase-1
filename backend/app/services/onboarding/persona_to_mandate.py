"""
Persona → Mandate pre-fill bridge.

prefill_mandate_from_persona: maps persona fields to a MandateDelta that
can be applied to a new (or incomplete) mandate. Called in two places:
  1. POST /api/v1/mandates — immediately after mandate record is created
  2. POST /api/v1/mandates/{id}/confirm — before completeness check

Rules:
  - NEVER overwrite a field with source="explicit"
  - NEVER overwrite a field with source="inferred" and confidence > 0.8
  - All applied fields get source="persona"
  - Only apply when the target field is empty or low-confidence
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class MandateDelta:
    """Structured pre-fill result ready to be applied to a mandate."""

    location: str | None = None
    soft_preferences: list[dict] = field(default_factory=list)
    dealbreakers: list[str] = field(default_factory=list)
    negotiation_range_floor: float | None = None
    negotiation_range_ceiling: float | None = None
    # Which mandate fields were touched (for audit / activity log)
    fields_applied: list[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.fields_applied


def prefill_mandate_from_persona(
    persona: dict,
    vertical: str | None = None,
    existing_mandate: dict | None = None,
) -> MandateDelta:
    """
    Map persona fields to mandate pre-fill delta.

    Args:
        persona:          Current users.persona blob.
        vertical:         "goods" | "services" | None — determines which budget
                          key to apply and whether has_pets is relevant.
        existing_mandate: Optional dict with current mandate state used to check
                          source flags before overwriting.

    Returns a MandateDelta. Apply it to the mandate with source="persona".
    """
    delta = MandateDelta()
    existing = existing_mandate or {}

    # ── Location ─────────────────────────────────────────────────────────────
    location = persona.get("location", {})
    if (
        location.get("neighborhood")
        and location.get("city")
        and not _is_protected(existing, "location")
    ):
        parts = [location.get("neighborhood"), location.get("city"), location.get("state")]
        delta.location = ", ".join(p for p in parts if p)
        delta.fields_applied.append("location")

    prefs = persona.get("preferences", {})

    # ── Style affinities → soft_preferences ──────────────────────────────────
    for style in prefs.get("style_affinities", []):
        delta.soft_preferences.append(
            {"attribute": "style", "value": style, "weight": 0.7, "source": "persona"}
        )
        delta.fields_applied.append(f"soft_preferences.style.{style}")

    # ── Style dealbreakers → dealbreakers ─────────────────────────────────────
    for dealbreaker in prefs.get("style_dealbreakers", []):
        delta.dealbreakers.append(dealbreaker)
        delta.fields_applied.append(f"dealbreakers.{dealbreaker}")

    # ── Budget → negotiation_range (vertical-gated, not already protected) ───
    if not _is_protected(existing, "negotiation_range"):
        budget: dict | None = None
        if vertical == "goods":
            budget = prefs.get("typical_budget_goods")
        elif vertical == "services":
            budget = prefs.get("typical_budget_services")

        if budget:
            delta.negotiation_range_floor = budget.get("floor", 0)
            delta.negotiation_range_ceiling = budget.get("ceiling")
            delta.fields_applied.append("negotiation_range")

    # ── has_pets → soft_preferences (goods mandates only) ────────────────────
    lifestyle = persona.get("lifestyle", {})
    if vertical == "goods" and lifestyle.get("has_pets") is True:
        delta.soft_preferences.append(
            {"attribute": "pet_friendly", "value": True, "weight": 0.6, "source": "persona"}
        )
        delta.fields_applied.append("soft_preferences.pet_friendly")

    return delta


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _is_protected(mandate: dict, field_name: str) -> bool:
    """
    Return True if the mandate field must NOT be overwritten by a persona pre-fill.

    Protected when:
      - source_flags[field] == "explicit"  (owner stated directly)
      - any mandate_fields entry has source="inferred" and confidence > 0.8
    """
    source_flags: dict = mandate.get("source_flags", {})
    if source_flags.get(field_name) == "explicit":
        return True

    for mf in mandate.get("mandate_fields", []):
        if mf.get("field_name") == field_name:
            if mf.get("source") == "explicit":
                return True
            if mf.get("source") == "inferred" and (mf.get("confidence") or 0) > 0.8:
                return True
    return False
