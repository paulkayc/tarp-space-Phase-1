"""
Signal ingestion — ARCHITECTURE.md Section 5
Accepts accept/reject/escalation signals from owners on individual search results.
Logs to signals table. Triggers refiner if rejection implies mandate delta.

Never calls an LLM. All logic is rule-based.
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.models import Mandate, SearchResult, Signal
from app.observability.events import emit_signal_received
from app.services.signals.refiner import compute_mandate_delta, apply_mandate_delta


def process_signal(
    db: Session,
    owner_id: UUID,
    mandate_id: UUID,
    search_result_id: UUID,
    signal_type: str,
    reason: str | None,
) -> dict:
    """
    Persist the signal, optionally compute and apply a mandate delta.

    Returns a dict with signal_id and mandate_delta_applied.
    """
    # Verify search result exists and belongs to this mandate
    result = db.query(SearchResult).filter_by(id=search_result_id).first()
    if result is None:
        raise ValueError(f"SearchResult {search_result_id} not found")

    mandate = db.query(Mandate).filter_by(id=mandate_id, owner_id=owner_id).first()
    if mandate is None:
        raise ValueError(f"Mandate {mandate_id} not found or not owned by user")

    # Compute mandate delta from signal (rule-based, no LLM)
    mandate_delta = compute_mandate_delta(signal_type=signal_type, reason=reason, mandate=mandate)

    now = datetime.now(timezone.utc)
    signal = Signal(
        id=uuid4(),
        owner_id=owner_id,
        search_result_id=search_result_id,
        signal_type=signal_type,
        reason=reason,
        mandate_delta_applied=mandate_delta or {},
        mandate_version_after=mandate.version,
        created_at=now,
    )
    db.add(signal)

    # Apply delta to mandate if there is one
    if mandate_delta:
        apply_mandate_delta(
            db=db,
            mandate=mandate,
            delta=mandate_delta,
            trigger_signal_id=str(signal.id),
        )
        signal.mandate_version_after = mandate.version

    db.commit()
    db.refresh(signal)

    # Emit observability event
    emit_signal_received(
        owner_id=str(owner_id),
        search_result_id=str(search_result_id),
        signal_type=signal_type,
        reason=reason,
        mandate_delta_applied=mandate_delta,
    )

    return {
        "signal_id": str(signal.id),
        "signal_type": signal_type,
        "mandate_delta_applied": mandate_delta or {},
        "mandate_version_after": signal.mandate_version_after,
    }
