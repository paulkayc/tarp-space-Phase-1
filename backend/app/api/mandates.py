from datetime import datetime, timezone
from time import monotonic
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.config import settings
from app.db.models import ActivityLog, Inventory, Mandate, SearchResult, SearchRun, User
from app.db.session import get_db
from app.agents.mandate_agent.gap_analyzer import compute_mandate_completeness, derive_mandate_state
from app.services.mandate.crud import prefill_mandate_from_persona
from app.services.privacy.gate import gate, _extract_price_ceiling
from app.services.matching.filter import hard_filter
from app.services.matching.ranker import rank_candidates
from app.services.matching.escalation import flag_escalations
from app.services.signals.processor import process_signal
from app.observability.events import (
    emit_search_started,
    emit_search_completed,
    emit_escalation_triggered,
)


def compute_completeness_score(mandate: Mandate) -> float:  # type: ignore[type-arg]
    return compute_mandate_completeness(derive_mandate_state(mandate))


router = APIRouter()


CONFIRM_LOW_SCORE_RESPONSE = {
    "error": "validation_error",
    "message": "Mandate completeness score too low to confirm",
    "details": {"current_score": 0.0, "required_score": 0.70},
}


def _serialize_mandate(mandate: Mandate) -> dict:
    status = "confirmed" if (mandate.is_active or mandate.confirmed_at is not None) else "draft"
    return {
        "id": str(mandate.id),
        "owner_id": str(mandate.owner_id),
        "intent_type": mandate.intent_type,
        "vertical": mandate.vertical,
        "category": mandate.category,
        "description": mandate.description,
        "hard_constraints": mandate.hard_constraints or [],
        "negotiation_range": mandate.negotiation_range or [],
        "soft_preferences": mandate.soft_preferences or [],
        "dealbreakers": mandate.dealbreakers or [],
        "escalation_triggers": mandate.escalation_triggers or [],
        "autonomy_level": mandate.autonomy_level,
        "completeness_score": float(mandate.completeness_score or 0.0),
        "status": status,
        "version": mandate.version,
        "confirmed_at": mandate.confirmed_at,
        "created_at": mandate.created_at,
        "updated_at": mandate.updated_at,
    }


def _get_mandate(db: Session, mandate_id: UUID) -> Mandate | None:
    return db.query(Mandate).filter_by(id=mandate_id).first()


def _get_owned_mandate_or_raise(db: Session, mandate_id: UUID, owner_id: UUID) -> Mandate:
    mandate = _get_mandate(db, mandate_id)
    if mandate is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": "Mandate not found"},
        )
    if mandate.owner_id != owner_id:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "You do not own this mandate"},
        )
    return mandate


@router.get("")
def list_mandates(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandates = db.query(Mandate).filter_by(owner_id=current_user.id).all()
    mandates.sort(key=lambda item: item.created_at, reverse=True)
    return {
        "mandates": [_serialize_mandate(m) for m in mandates],
        "next_cursor": None,
        "total": len(mandates),
    }


@router.post("", status_code=201)
def create_mandate(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    now = datetime.now(timezone.utc)
    mandate = Mandate(
        owner_id=current_user.id,
        hard_constraints=[],
        negotiation_range=[],
        soft_preferences=[],
        dealbreakers=[],
        escalation_triggers=[],
        completeness_score=0.0,
        is_active=False,
        is_archived=False,
        version=1,
        created_at=now,
        updated_at=now,
    )
    prefill_mandate_from_persona(mandate, current_user)
    mandate.completeness_score = compute_completeness_score(mandate)
    db.add(mandate)
    db.commit()
    db.refresh(mandate)
    return _serialize_mandate(mandate)


@router.get("/{mandate_id}")
def get_mandate(
    mandate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandate = _get_owned_mandate_or_raise(db, mandate_id, current_user.id)
    return _serialize_mandate(mandate)


@router.post("/{mandate_id}/confirm")
def confirm_mandate(
    mandate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    mandate = _get_owned_mandate_or_raise(db, mandate_id, current_user.id)
    mandate.completeness_score = compute_completeness_score(mandate)
    current_score = float(mandate.completeness_score or 0.0)
    if current_score < settings.completeness_threshold:
        return JSONResponse(
            status_code=422,
            content={
                **CONFIRM_LOW_SCORE_RESPONSE,
                "details": {
                    "current_score": round(current_score, 3),
                    "required_score": round(float(settings.completeness_threshold), 2),
                },
            },
        )

    now = datetime.now(timezone.utc)
    mandate.is_active = True
    mandate.confirmed_at = now
    mandate.updated_at = now
    db.commit()
    db.refresh(mandate)
    return _serialize_mandate(mandate)


@router.post("/{mandate_id}/search")
def search_mandate(
    mandate_id: UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Run the full matching pipeline against seeded inventory.

    Pipeline:
      1. Privacy gate — validate mandate, sanitize signals, log gate decisions
      2. Hard filter — eliminate non-matching inventory
      3. Semantic ranker — pgvector cosine similarity (text fallback without embeddings)
      4. Escalation flagging — items above ceiling within threshold
      5. Persist SearchRun + SearchResult records
      6. Emit observability events
      7. Return ranked results
    """
    mandate = _get_owned_mandate_or_raise(db, mandate_id, current_user.id)

    search_id = str(uuid4())
    start_time = monotonic()

    # Emit search_started event
    emit_search_started(
        mandate_id=str(mandate.id),
        mandate_version=mandate.version,
        search_id=search_id,
    )

    # Step 1: Privacy gate
    sanitized_signal, gate_passed = gate(mandate)
    if not gate_passed:
        problems = sanitized_signal.get("problems", [])
        raise HTTPException(
            status_code=422,
            detail={
                "error": "privacy_gate_blocked",
                "message": "Mandate failed privacy gate validation",
                "details": {"problems": problems},
            },
        )

    # Step 2: Load all active inventory
    all_inventory: list[Inventory] = db.query(Inventory).filter_by(is_active=True).all()
    candidates_pre_filter = len(all_inventory)

    # Step 3: Hard constraint filter
    passed_items, escalation_candidates = hard_filter(all_inventory, mandate)
    candidates_post_filter = len(passed_items)

    # Step 4: Semantic ranker (top N)
    price_ceiling = _extract_price_ceiling(mandate)
    ranked_results = rank_candidates(
        candidates=passed_items,
        mandate_description=mandate.description,
        mandate_embedding=None,  # Phase 1: no real-time embedding generation
        price_ceiling=price_ceiling,
        top_n=settings.match_top_n,
    )

    # Step 5: Escalation flagging
    escalations = flag_escalations(
        escalation_candidates=escalation_candidates,
        mandate=mandate,
        mandate_description=mandate.description,
        mandate_embedding=None,
    )

    # Step 6: Persist SearchRun
    now = datetime.now(timezone.utc)
    top_score = ranked_results[0][1] if ranked_results else 0.0
    latency_ms = int((monotonic() - start_time) * 1000)

    search_run = SearchRun(
        id=uuid4(),
        mandate_id=mandate.id,
        mandate_version=mandate.version,
        candidates_pre_filter=candidates_pre_filter,
        candidates_post_filter=candidates_post_filter,
        result_count=len(ranked_results),
        escalation_count=len(escalations),
        top_score=round(top_score, 4),
        latency_ms=latency_ms,
        created_at=now,
    )
    db.add(search_run)
    db.flush()  # get search_run.id without full commit

    # Persist SearchResult rows
    result_rows: list[SearchResult] = []
    for item, alignment_score, matched_dims in ranked_results:
        result_row = SearchResult(
            id=uuid4(),
            search_run_id=search_run.id,
            listing_id=item.id,
            similarity_score=round(alignment_score, 4),
            trust_weight=0.0,
            alignment_score=round(alignment_score, 4),
            within_mandate=True,
            matched_dimensions=matched_dims,
            explanation=_build_explanation(item, matched_dims),
            is_escalation=False,
            created_at=now,
        )
        db.add(result_row)
        result_rows.append(result_row)

    # Persist escalation SearchResult rows
    escalation_rows: list[tuple[SearchResult, dict]] = []
    for esc in escalations:
        esc_item = esc["inventory_item"]
        esc_result = SearchResult(
            id=uuid4(),
            search_run_id=search_run.id,
            listing_id=esc_item.id,
            similarity_score=round(esc["alignment_score"], 4),
            trust_weight=0.0,
            alignment_score=round(esc["alignment_score"], 4),
            within_mandate=False,
            matched_dimensions=["category", "vertical"],
            explanation=None,
            is_escalation=True,
            escalation_delta=esc["threshold_delta"],
            escalation_question=esc["question"],
            created_at=now,
        )
        db.add(esc_result)
        escalation_rows.append((esc_result, esc))

    db.commit()

    # Emit escalation_triggered events (after commit so IDs are stable)
    for esc_result, esc_data in escalation_rows:
        emit_escalation_triggered(
            search_id=str(search_run.id),
            result_id=str(esc_result.id),
            listing_id=str(esc_data["inventory_item"].id),
            threshold_delta=esc_data["threshold_delta"],
            question_text=esc_data["question"],
        )

    # Emit search_completed event
    emit_search_completed(
        search_id=str(search_run.id),
        mandate_id=str(mandate.id),
        candidate_count_pre_filter=candidates_pre_filter,
        candidate_count_post_filter=candidates_post_filter,
        top_score=float(top_score),
        latency_ms=latency_ms,
    )

    # Build response
    results_payload = []
    for (item, alignment_score, matched_dims), result_row in zip(ranked_results, result_rows):
        results_payload.append({
            "result_id": str(result_row.id),
            "listing_id": str(item.id),
            "title": item.title,
            "category": item.category,
            "price": float(item.price),
            "location": item.location_raw,
            "alignment_score": alignment_score,
            "within_mandate": True,
            "matched_dimensions": matched_dims,
            "explanation": result_row.explanation,
            "escalation": None,
        })

    escalations_payload = []
    for esc_result, esc in escalation_rows:
        esc_item = esc["inventory_item"]
        escalations_payload.append({
            "result_id": str(esc_result.id),
            "listing_id": str(esc_item.id),
            "title": esc_item.title,
            "category": esc_item.category,
            "price": float(esc_item.price),
            "location": esc_item.location_raw,
            "alignment_score": esc["alignment_score"],
            "within_mandate": False,
            "threshold_delta": esc["threshold_delta"],
            "question": esc["question"],
        })

    return {
        "search_id": str(search_run.id),
        "mandate_id": str(mandate.id),
        "mandate_version": mandate.version,
        "candidates_pre_filter": candidates_pre_filter,
        "candidates_post_filter": candidates_post_filter,
        "results": results_payload,
        "escalations": escalations_payload,
        "latency_ms": latency_ms,
    }


class SignalRequest(BaseModel):
    search_result_id: UUID
    signal_type: str
    reason: str | None = None


@router.post("/{mandate_id}/signals")
def submit_signal(
    mandate_id: UUID,
    body: SignalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Submit an accept/reject/escalation signal for a search result."""
    valid_types = {"accept", "reject", "escalation_yes", "escalation_no"}
    if body.signal_type not in valid_types:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "validation_error",
                "message": f"signal_type must be one of {sorted(valid_types)}",
            },
        )

    try:
        result = process_signal(
            db=db,
            owner_id=current_user.id,
            mandate_id=mandate_id,
            search_result_id=body.search_result_id,
            signal_type=body.signal_type,
            reason=body.reason,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=404,
            detail={"error": "not_found", "message": str(exc)},
        )

    return result


def _build_explanation(item: Inventory, matched_dims: list[str]) -> str:
    """Build a simple template-based explanation for a matched result."""
    parts: list[str] = []
    meta = item.metadata_json or {}

    if "category" in matched_dims:
        parts.append(f"Category match: {item.category}")
    if "price" in matched_dims:
        parts.append(f"price ${item.price:.0f} within your range")
    if "location" in matched_dims and item.location_raw:
        parts.append(f"located in {item.location_raw}")
    if "condition" in matched_dims and meta.get("condition"):
        parts.append(f"condition: {meta['condition']}")
    if "style" in matched_dims:
        style = meta.get("style") or meta.get("aesthetic", "")
        if style:
            parts.append(f"style: {style}")

    if not parts:
        return f"Matches your {item.category} search."

    explanation = "; ".join(parts).capitalize() + "."
    return explanation
