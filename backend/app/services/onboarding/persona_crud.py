"""
Persona DB operations — load and save the users.persona JSONB blob.

save_persona_delta: deep-merges a delta into the existing persona, recomputes
  the completeness score, persists, and emits a persona_updated activity event.

get_persona: returns the current persona for a user.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.db.models import ActivityLog, User
from app.services.onboarding.gap_analyzer import compute_completeness_score


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_persona(db: Session, owner_id: str) -> dict:
    """Return users.persona for this external_user_id, or {} if not found."""
    user = _get_user(db, owner_id)
    return dict(user.persona) if user and user.persona else {}


def save_persona_delta(db: Session, owner_id: str, delta: dict) -> dict:
    """
    Deep-merge delta into the existing persona, recompute completeness, save.

    Side effects:
      - updates users.persona and users.updated_at
      - sets users.onboarding_completed_at if score >= 0.7 and not yet set
      - writes a persona_updated event to activity_log

    Returns the updated persona dict.
    """
    user = _get_user(db, owner_id)
    if user is None:
        raise ValueError(f"User not found for external_user_id={owner_id!r}")

    current = dict(user.persona) if user.persona else {}
    flat_before = set(_flatten_keys(current))

    merged = _deep_merge(current, delta)
    score = compute_completeness_score(merged)
    now = datetime.now(timezone.utc)
    merged["completeness_score"] = score
    merged["collected_at"] = now.isoformat()

    flat_after = set(_flatten_keys(merged))
    fields_added = sorted(
        flat_after - flat_before - {"completeness_score", "collected_at"}
    )

    user.persona = merged
    user.updated_at = now

    if score >= 0.7 and user.onboarding_completed_at is None:
        user.onboarding_completed_at = now

    db.add(
        ActivityLog(
            owner_id=user.id,
            event_type="persona_updated",
            payload={"fields_added": fields_added, "new_completeness_score": score},
            created_at=now,
        )
    )
    db.commit()
    db.refresh(user)
    return dict(user.persona)


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------

def _get_user(db: Session, owner_id: str) -> User | None:
    return db.query(User).filter(User.external_user_id == owner_id).first()


def _deep_merge(base: dict, delta: dict) -> dict:
    """
    Recursively merge delta into base.
    - Nested dicts are merged recursively.
    - Lists are unioned (no duplicates, order preserved).
    - Scalar values in delta overwrite base.
    """
    result = dict(base)
    for key, value in delta.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge(existing, value)
        elif isinstance(existing, list) and isinstance(value, list):
            seen = set()
            merged_list = []
            for item in existing + value:
                item_key = item if not isinstance(item, dict) else str(sorted(item.items()))
                if item_key not in seen:
                    seen.add(item_key)
                    merged_list.append(item)
            result[key] = merged_list
        else:
            result[key] = value
    return result


def _flatten_keys(d: dict, prefix: str = "") -> list[str]:
    """Return dot-notation paths for all leaf values in a nested dict."""
    keys: list[str] = []
    for k, v in d.items():
        full_key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            keys.extend(_flatten_keys(v, full_key))
        else:
            keys.append(full_key)
    return keys
