"""
Onboarding gap analyzer — rule-based, no LLM.

Identifies the next unfilled priority field to ask about, and computes
the persona completeness score.

Priority order (from spec):
  1. display_name
  2. neighborhood
  3. sex              (optional — skip if declined)
  4. has_pets
  5. home_type
  6. style_affinities
  7. style_dealbreakers
  8. typical_budget_goods
  9. community_names
  10. phone            (optional — skip if declined)
"""
from __future__ import annotations

COMPLETENESS_THRESHOLD = 0.7

# (dot_path_into_persona, default_question_text)
_PRIORITY: list[tuple[str, str]] = [
    ("identity.display_name", "What should I call you?"),
    (
        "location.neighborhood",
        "What part of Houston are you in?",
    ),
    (
        "identity.sex",
        "Optional — what's your gender? You can skip this.",
    ),
    ("lifestyle.has_pets", "Do you have any pets?"),
    (
        "lifestyle.home_type",
        "Do you rent or own — apartment, house, or condo?",
    ),
    (
        "preferences.style_affinities",
        "What furniture styles do you love?",
    ),
    (
        "preferences.style_dealbreakers",
        "Anything you absolutely can't stand style-wise?",
    ),
    (
        "preferences.typical_budget_goods",
        "Roughly what do you spend on furniture — are you a $50-thrift-store person "
        "or more like a $500-quality-piece person?",
    ),
    (
        "trust_seeds.community_names",
        "Are you part of any local groups, alumni networks, or neighborhood associations?",
    ),
    (
        "identity.phone",
        "Last one — what's your phone number? Purely optional.",
    ),
]

# Fields the user can explicitly decline; once declined they are never asked again.
_OPTIONAL_FIELDS = {"identity.sex", "identity.phone"}


def compute_completeness_score(persona: dict) -> float:
    """
    Weighted completeness score for the persona blob.

    Weights (from spec):
      identity.display_name set          → +0.20
      location.neighborhood set          → +0.25
      preferences: style OR budget       → +0.20
      lifestyle: has_pets AND home_type  → +0.20
      trust_seeds: community_name(s)     → +0.15
                                           ------
      Max                                   1.00
    """
    score = 0.0

    identity = persona.get("identity", {})
    if identity.get("display_name"):
        score += 0.20

    location = persona.get("location", {})
    if location.get("neighborhood"):
        score += 0.25

    prefs = persona.get("preferences", {})
    has_style = bool(prefs.get("style_affinities"))
    has_budget = bool(
        prefs.get("typical_budget_goods") or prefs.get("typical_budget_services")
    )
    if has_style or has_budget:
        score += 0.20

    lifestyle = persona.get("lifestyle", {})
    if lifestyle.get("has_pets") is not None and lifestyle.get("home_type"):
        score += 0.20

    trust = persona.get("trust_seeds", {})
    if trust.get("community_names"):
        score += 0.15

    return round(score, 3)


def _get_nested(data: dict, dot_path: str):
    """Return the value at a dot-notation path, or None if missing."""
    parts = dot_path.split(".")
    cur = data
    for part in parts:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(part)
    return cur


def _is_declined(persona: dict, dot_path: str) -> bool:
    """Return True if the user has previously declined to answer this field."""
    return dot_path in persona.get("_meta", {}).get("declined", [])


def _is_filled(persona: dict, dot_path: str) -> bool:
    """Return True if the field at dot_path has a non-empty value."""
    value = _get_nested(persona, dot_path)
    if value is None:
        return False
    if isinstance(value, (list, dict)):
        return bool(value)
    if isinstance(value, bool):
        return True  # False is a valid answer for has_pets
    return bool(str(value).strip())


def find_next_gap(persona: dict) -> tuple[str | None, str | None]:
    """
    Return (dot_path, question) for the highest-priority unfilled field.

    Returns (None, None) when completeness_score >= COMPLETENESS_THRESHOLD
    or when all fields are either filled or declined.

    sex and phone are skipped if previously declined — never asked again.
    """
    if compute_completeness_score(persona) >= COMPLETENESS_THRESHOLD:
        return None, None

    for dot_path, question in _PRIORITY:
        if _is_declined(persona, dot_path):
            continue
        if _is_filled(persona, dot_path):
            continue
        return dot_path, question

    return None, None


def mark_declined(persona: dict, dot_path: str) -> dict:
    """
    Return a copy of persona with dot_path added to the declined list.
    Only valid for optional fields (sex, phone).
    """
    if dot_path not in _OPTIONAL_FIELDS:
        raise ValueError(f"{dot_path!r} is not an optional field and cannot be declined")
    meta = dict(persona.get("_meta", {}))
    declined = list(meta.get("declined", []))
    if dot_path not in declined:
        declined.append(dot_path)
    meta["declined"] = declined
    return {**persona, "_meta": meta}
