"""
Central event emitter — ARCHITECTURE.md Section 10.

emit_event(event_type, payload, owner_id, mandate_id, db)

Two outputs on every call:
  1. structlog JSON line to stdout
  2. INSERT into activity_log (when db session provided)

Never raises. DB failures are caught and logged to stdout so observability
never blocks the request path.

Event types used in onboarding:
  persona_created   — first write to an empty persona
  persona_updated   — every save_persona_delta call
  onboarding_completed — session completes or skips
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

import structlog
from sqlalchemy.orm import Session

from app.db.models import ActivityLog

logger = structlog.get_logger(__name__)


def emit_event(
    event_type: str,
    payload: dict,
    owner_id: uuid.UUID | None = None,
    mandate_id: uuid.UUID | None = None,
    db: Session | None = None,
) -> None:
    """
    Emit a structured event to stdout + activity_log.

    Never raises — all errors are caught and logged.
    """
    now = datetime.now(timezone.utc)

    # ── 1. Structured log to stdout ──────────────────────────────────────────
    try:
        logger.info(
            event_type,
            event=event_type,
            owner_id=str(owner_id) if owner_id is not None else None,
            mandate_id=str(mandate_id) if mandate_id is not None else None,
            payload=payload,
            timestamp=now.isoformat(),
        )
    except Exception as exc:  # pragma: no cover
        print(f"[emit_event] structlog error: {exc}")

    # ── 2. Persist to activity_log ───────────────────────────────────────────
    if db is None:
        return

    try:
        log = ActivityLog(
            owner_id=owner_id,
            mandate_id=mandate_id,
            event_type=event_type,
            payload=payload,
            created_at=now,
        )
        db.add(log)
        db.commit()
    except Exception as exc:
        try:
            db.rollback()
        except Exception:
            pass
        logger.error(
            "emit_event_db_error",
            event_type=event_type,
            error=str(exc),
        )
