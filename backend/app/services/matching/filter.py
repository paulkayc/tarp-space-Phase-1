"""
Hard constraint filter — ARCHITECTURE.md Section 3.4, Stage 1
No LLM. Deterministic elimination of candidates that violate any
hard constraint or dealbreaker. Target latency: < 100ms on 500 listings.

Takes a list of Inventory objects and the raw Mandate (local computation only —
constraint values never transmitted externally per privacy gate rules).

Returns:
  passed: list of items that pass all hard constraints
  escalation_candidates: items that fail only because price is above ceiling
    but within the escalation threshold (ceiling * (1 + ESCALATION_THRESHOLD_PCT))
"""
from __future__ import annotations

from app.core.config import settings
from app.db.models import Inventory, Mandate
from app.services.privacy.gate import _extract_location_string, _extract_price_ceiling


def _category_matches(item: Inventory, mandate: Mandate) -> bool:
    """Category match is case-insensitive substring check."""
    if not mandate.category:
        return True
    mandate_cat = mandate.category.lower().strip()
    item_cat = item.category.lower().strip()
    return mandate_cat == item_cat or mandate_cat in item_cat or item_cat in mandate_cat


def _vertical_matches(item: Inventory, mandate: Mandate) -> bool:
    if not mandate.vertical:
        return True
    return item.vertical == mandate.vertical


def _location_matches(item: Inventory, location_str: str | None) -> bool:
    """
    Phase 1: simple string match on location_raw.
    Phase 2 will use PostGIS ST_DWithin for radius queries.
    """
    if not location_str:
        return True
    if not item.location_raw:
        return True  # No location on item = not filtered by location
    return location_str.lower() in item.location_raw.lower()


def _violates_dealbreaker(item: Inventory, mandate: Mandate) -> bool:
    """
    Check if item violates any mandate dealbreaker.
    Only field names checked against item metadata (values never transmitted).
    """
    meta = item.metadata_json or {}
    for db_item in (mandate.dealbreakers or []):
        if not isinstance(db_item, dict):
            continue
        field = db_item.get("field")
        value = db_item.get("value")
        if not field:
            continue
        # Check in item metadata
        item_val = meta.get(field)
        if item_val is not None and value is not None:
            # Dealbreaker match: item has this field set to the disqualifying value
            if str(item_val).lower() == str(value).lower():
                return True
    return False


def hard_filter(
    candidates: list[Inventory],
    mandate: Mandate,
) -> tuple[list[Inventory], list[Inventory]]:
    """
    Stage 1 filter: eliminate candidates that violate hard constraints.

    Returns:
        passed: items that pass all constraints
        escalation_candidates: items that fail only on price, but within escalation threshold
    """
    price_ceiling = _extract_price_ceiling(mandate)
    location_str = _extract_location_string(mandate)

    passed: list[Inventory] = []
    escalation_candidates: list[Inventory] = []

    for item in candidates:
        if not item.is_active:
            continue

        # 1. Vertical check
        if not _vertical_matches(item, mandate):
            continue

        # 2. Category check
        if not _category_matches(item, mandate):
            continue

        # 3. Location check (Phase 1: string match, Phase 2: PostGIS radius)
        if not _location_matches(item, location_str):
            continue

        # 4. Dealbreaker check (evaluated locally, never transmitted raw)
        if _violates_dealbreaker(item, mandate):
            continue

        # 5. Price check
        if price_ceiling is not None:
            item_price = float(item.price)
            if item_price > price_ceiling:
                # Check escalation threshold
                threshold = price_ceiling * (1.0 + settings.escalation_threshold_pct)
                if item_price <= threshold:
                    escalation_candidates.append(item)
                # Either way, item fails the hard constraint filter
                continue

        passed.append(item)

    return passed, escalation_candidates
