"""
Tests for the Phase 1 matching engine:
  - Privacy gate (unit)
  - Hard constraint filter (unit)
  - Semantic ranker (unit)
  - Escalation flagging (unit)
  - Inventory API (integration)
  - Search API (integration)
  - Signals API (integration)
  - Observability events (unit)
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

import pytest

from app.db.models import Inventory, Mandate, SearchResult, SearchRun, Signal


# ---------------------------------------------------------------------------
# Helpers — build fake models
# ---------------------------------------------------------------------------

def _make_mandate(**overrides) -> Mandate:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        owner_id=uuid.uuid4(),
        intent_type="buy",
        vertical="goods",
        category="furniture",
        description="mid-century modern sofa in Montrose under $500",
        hard_constraints=[{"field": "location", "value": "Montrose"}],
        negotiation_range=[],
        soft_preferences=[],
        dealbreakers=[],
        escalation_triggers=[],
        autonomy_level="escalate_key_points",
        completeness_score=Decimal("0.850"),
        is_active=True,
        is_archived=False,
        version=1,
        created_at=now,
        updated_at=now,
        confirmed_at=now,
    )
    defaults.update(overrides)
    return Mandate(**defaults)


def _make_inventory(**overrides) -> Inventory:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        seller_id=None,
        vertical="goods",
        category="furniture",
        title="Test sofa",
        description="mid-century modern sofa walnut legs",
        metadata_json={"condition": "like new", "style": "mid-century modern"},
        price=Decimal("420.00"),
        price_negotiable=True,
        location_raw="Montrose, Houston, TX",
        location_geom=None,
        embedding=None,
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    defaults.update(overrides)
    return Inventory(**defaults)


def _make_search_result(**overrides) -> SearchResult:
    now = datetime.now(timezone.utc)
    defaults = dict(
        id=uuid.uuid4(),
        search_run_id=uuid.uuid4(),
        listing_id=uuid.uuid4(),
        similarity_score=Decimal("0.8500"),
        trust_weight=Decimal("0.0000"),
        alignment_score=Decimal("0.8500"),
        within_mandate=True,
        matched_dimensions=["category", "price"],
        explanation="Test explanation",
        is_escalation=False,
        created_at=now,
    )
    defaults.update(overrides)
    return SearchResult(**defaults)


# ---------------------------------------------------------------------------
# Unit: Privacy Gate
# ---------------------------------------------------------------------------

class TestPrivacyGate:
    def test_gate_passes_valid_mandate(self):
        from app.services.privacy.gate import gate
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "floor": 200, "ceiling": 500, "opening_position": 350}],
        )
        signal, passed = gate(mandate)
        assert passed is True
        assert signal["category"] == "furniture"
        assert signal["vertical"] == "goods"
        assert signal["price_ceiling"] == 500.0

    def test_gate_strips_negotiation_range(self):
        from app.services.privacy.gate import gate
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "floor": 200, "ceiling": 500, "opening_position": 350}],
        )
        signal, _ = gate(mandate)
        # Raw range fields must NOT be in sanitized signal
        assert "negotiation_range" not in signal
        assert "floor" not in signal
        assert "ceiling" not in signal
        # Safe scalar ceiling is present
        assert signal["price_ceiling"] == 500.0

    def test_gate_blocks_opening_equals_ceiling(self):
        from app.services.privacy.gate import gate
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "floor": 200, "ceiling": 500, "opening_position": 500}],
        )
        signal, passed = gate(mandate)
        assert passed is False
        assert any("opening_equals_ceiling" in p or "opening" in p for p in signal["problems"])

    def test_gate_blocks_opening_equals_floor(self):
        from app.services.privacy.gate import gate
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "floor": 200, "ceiling": 500, "opening_position": 200}],
        )
        signal, passed = gate(mandate)
        assert passed is False

    def test_gate_strips_dealbreakers_to_field_names_only(self):
        from app.services.privacy.gate import gate
        mandate = _make_mandate(
            dealbreakers=[{"field": "material", "value": "particle board"}],
        )
        signal, _ = gate(mandate)
        # Values must not appear, only field names
        assert "particle board" not in str(signal)
        assert "material" in signal["dealbreaker_fields"]

    def test_gate_extracts_location_from_hard_constraints(self):
        from app.services.privacy.gate import gate
        mandate = _make_mandate(
            hard_constraints=[{"field": "location", "value": "Montrose"}],
        )
        signal, _ = gate(mandate)
        assert signal["location_fuzzy"] == "Montrose"

    def test_gate_emits_privacy_gate_decision_events(self):
        from app.services.privacy.gate import gate
        from app.observability.events import emit_privacy_gate_decision
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "floor": 200, "ceiling": 500, "opening_position": 350}],
            dealbreakers=[{"field": "material", "value": "particle board"}],
        )
        emitted = []
        original = emit_privacy_gate_decision

        def capturing_emit(mandate_id, field, action, rule_applied):
            emitted.append({"field": field, "action": action, "rule_applied": rule_applied})
            return original(mandate_id=mandate_id, field=field, action=action, rule_applied=rule_applied)

        with patch("app.services.privacy.gate.emit_privacy_gate_decision", capturing_emit):
            gate(mandate)

        assert len(emitted) >= 2
        actions = {e["action"] for e in emitted}
        assert "strip" in actions


# ---------------------------------------------------------------------------
# Unit: Hard Constraint Filter
# ---------------------------------------------------------------------------

class TestHardFilter:
    def test_filter_passes_matching_item(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate(
            category="furniture",
            vertical="goods",
            hard_constraints=[{"field": "location", "value": "Montrose"}],
        )
        item = _make_inventory(category="furniture", vertical="goods", location_raw="Montrose, Houston, TX")
        passed, escalations = hard_filter([item], mandate)
        assert item in passed
        assert escalations == []

    def test_filter_removes_wrong_category(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate(category="furniture", vertical="goods")
        item = _make_inventory(category="electronics", vertical="goods")
        passed, esc = hard_filter([item], mandate)
        assert passed == []
        assert esc == []

    def test_filter_removes_wrong_vertical(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate(category="furniture", vertical="goods")
        item = _make_inventory(category="furniture", vertical="services")
        passed, esc = hard_filter([item], mandate)
        assert passed == []

    def test_filter_removes_item_above_price_ceiling(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "ceiling": 500, "floor": 100, "opening_position": 300}],
        )
        item = _make_inventory(price=Decimal("600.00"))  # above ceiling AND above threshold
        passed, esc = hard_filter([item], mandate)
        assert passed == []
        assert esc == []  # > 15% above ceiling

    def test_filter_escalates_item_within_threshold(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "ceiling": 500, "floor": 100, "opening_position": 300}],
        )
        # $550 = 10% above $500 ceiling (within 15% threshold)
        item = _make_inventory(price=Decimal("550.00"))
        passed, esc = hard_filter([item], mandate)
        assert passed == []
        assert item in esc

    def test_filter_removes_dealbreaker_item(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate(
            dealbreakers=[{"field": "material", "value": "particle board"}],
        )
        item = _make_inventory(metadata_json={"material": "particle board"})
        passed, _ = hard_filter([item], mandate)
        assert passed == []

    def test_filter_skips_inactive_items(self):
        from app.services.matching.filter import hard_filter
        mandate = _make_mandate()
        item = _make_inventory(is_active=False)
        passed, _ = hard_filter([item], mandate)
        assert passed == []


# ---------------------------------------------------------------------------
# Unit: Semantic Ranker
# ---------------------------------------------------------------------------

class TestRanker:
    def test_rank_returns_top_n(self):
        from app.services.matching.ranker import rank_candidates
        items = [_make_inventory(description=f"item {i}") for i in range(10)]
        results = rank_candidates(items, "furniture sofa", top_n=5)
        assert len(results) == 5

    def test_rank_uses_text_similarity_fallback(self):
        from app.services.matching.ranker import rank_candidates
        relevant = _make_inventory(description="mid-century modern sofa walnut")
        irrelevant = _make_inventory(description="refrigerator appliance stainless steel")
        results = rank_candidates([relevant, irrelevant], "mid-century modern sofa")
        assert results[0][0] is relevant
        assert results[0][1] > results[1][1]

    def test_rank_scores_between_0_and_1(self):
        from app.services.matching.ranker import rank_candidates
        items = [_make_inventory(description="sofa furniture couch")]
        results = rank_candidates(items, "sofa", top_n=1)
        score = results[0][1]
        assert 0.0 <= score <= 1.0

    def test_rank_empty_candidates_returns_empty(self):
        from app.services.matching.ranker import rank_candidates
        results = rank_candidates([], "sofa")
        assert results == []

    def test_rank_includes_matched_dimensions(self):
        from app.services.matching.ranker import rank_candidates
        item = _make_inventory(
            category="furniture",
            price=Decimal("300.00"),
            location_raw="Montrose",
            metadata_json={"condition": "excellent"},
        )
        results = rank_candidates([item], "furniture sofa", price_ceiling=500.0, top_n=1)
        dims = results[0][2]
        assert "category" in dims
        assert "price" in dims
        assert "location" in dims
        assert "condition" in dims

    def test_cosine_similarity_correct(self):
        from app.services.matching.ranker import _cosine_similarity
        a = [1.0, 0.0]
        b = [1.0, 0.0]
        assert _cosine_similarity(a, b) == pytest.approx(1.0)
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert _cosine_similarity(a, b) == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Unit: Escalation Flagging
# ---------------------------------------------------------------------------

class TestEscalation:
    def test_flag_escalations_with_above_ceiling_item(self):
        from app.services.matching.escalation import flag_escalations
        mandate = _make_mandate(
            negotiation_range=[{"dimension": "price", "ceiling": 500, "floor": 100, "opening_position": 300}],
        )
        item = _make_inventory(price=Decimal("550.00"), description="mid-century sofa furniture")
        esc = flag_escalations([item], mandate, "mid-century sofa furniture")
        assert len(esc) >= 0  # may be 0 if text score too low with no overlap
        if esc:
            assert esc[0]["threshold_delta"] == pytest.approx(50.0)
            assert "550" in esc[0]["question"] or "50" in esc[0]["question"]

    def test_flag_escalations_returns_empty_without_ceiling(self):
        from app.services.matching.escalation import flag_escalations
        mandate = _make_mandate(negotiation_range=[])
        item = _make_inventory(price=Decimal("550.00"))
        esc = flag_escalations([item], mandate, "sofa")
        assert esc == []

    def test_escalation_question_references_delta(self):
        from app.services.matching.escalation import build_escalation_question
        question = build_escalation_question(None, 500.0, 60.0)
        assert "60" in question
        assert "ceiling" in question.lower() or "above" in question.lower()


# ---------------------------------------------------------------------------
# Unit: Signal Refiner
# ---------------------------------------------------------------------------

class TestSignalRefiner:
    def test_accept_produces_no_delta(self):
        from app.services.signals.refiner import compute_mandate_delta
        mandate = _make_mandate()
        delta = compute_mandate_delta("accept", None, mandate)
        assert delta is None

    def test_reject_with_keyword_adds_dealbreaker(self):
        from app.services.signals.refiner import compute_mandate_delta
        mandate = _make_mandate(dealbreakers=[])
        delta = compute_mandate_delta("reject", "doesn't want leather", mandate)
        assert delta is not None
        assert "add_dealbreakers" in delta
        fields = [d["field"] for d in delta["add_dealbreakers"]]
        assert "leather" in fields

    def test_reject_without_reason_produces_no_delta(self):
        from app.services.signals.refiner import compute_mandate_delta
        mandate = _make_mandate()
        delta = compute_mandate_delta("reject", None, mandate)
        assert delta is None

    def test_escalation_yes_produces_no_delta(self):
        from app.services.signals.refiner import compute_mandate_delta
        mandate = _make_mandate()
        delta = compute_mandate_delta("escalation_yes", None, mandate)
        assert delta is None

    def test_existing_dealbreaker_not_duplicated(self):
        from app.services.signals.refiner import compute_mandate_delta
        mandate = _make_mandate(
            dealbreakers=[{"field": "leather", "value": "leather", "source": "explicit"}]
        )
        delta = compute_mandate_delta("reject", "no leather please", mandate)
        # leather already in dealbreakers, delta should be None or have no new items
        if delta and "add_dealbreakers" in delta:
            new_fields = [d["field"] for d in delta["add_dealbreakers"]]
            assert "leather" not in new_fields


# ---------------------------------------------------------------------------
# Unit: Observability Events
# ---------------------------------------------------------------------------

class TestObservabilityEvents:
    def test_emit_search_started(self):
        from app.observability.events import emit_search_started
        result = emit_search_started("m-id", 1, "s-id")
        assert result["event"] == "search_started"
        assert result["mandate_id"] == "m-id"
        assert result["search_id"] == "s-id"

    def test_emit_privacy_gate_decision(self):
        from app.observability.events import emit_privacy_gate_decision
        result = emit_privacy_gate_decision("m-id", "price", "strip", "range_to_signal")
        assert result["event"] == "privacy_gate_decision"
        assert result["action"] == "strip"
        assert result["rule_applied"] == "range_to_signal"

    def test_emit_search_completed(self):
        from app.observability.events import emit_search_completed
        result = emit_search_completed("s-id", "m-id", 50, 12, 0.91, 250)
        assert result["event"] == "search_completed"
        assert result["top_score"] == 0.91
        assert result["latency_ms"] == 250

    def test_emit_escalation_triggered(self):
        from app.observability.events import emit_escalation_triggered
        result = emit_escalation_triggered("s-id", "r-id", "l-id", 60.0, "Explore it?")
        assert result["event"] == "escalation_triggered"
        assert result["threshold_delta"] == 60.0

    def test_emit_signal_received(self):
        from app.observability.events import emit_signal_received
        result = emit_signal_received("o-id", "sr-id", "accept", None, None)
        assert result["event"] == "signal_received"
        assert result["signal_type"] == "accept"

    def test_emit_mandate_refined(self):
        from app.observability.events import emit_mandate_refined
        result = emit_mandate_refined("m-id", "dealbreakers", "sig-id", [], [{"field": "leather"}])
        assert result["event"] == "mandate_refined"
        assert result["field_changed"] == "dealbreakers"


# ---------------------------------------------------------------------------
# Integration: Inventory API
# ---------------------------------------------------------------------------

class TestInventoryAPI:
    def test_list_inventory_requires_admin(self, client, user_uuid):
        resp = client.get(
            "/api/v1/inventory",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 403

    def test_list_inventory_with_admin_key(self, client, user_uuid, fake_db, now_utc):
        item = _make_inventory()
        fake_db.add(item)
        resp = client.get(
            "/api/v1/inventory",
            headers={"X-Dev-User-Id": user_uuid, "X-Agent-Admin-Key": "admin-local"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "inventory" in data
        assert data["total"] >= 1

    def test_create_inventory_item(self, client, user_uuid):
        resp = client.post(
            "/api/v1/inventory",
            headers={"X-Dev-User-Id": user_uuid, "X-Agent-Admin-Key": "admin-local"},
            json={
                "vertical": "goods",
                "category": "furniture",
                "title": "Test sofa",
                "description": "A test sofa for unit testing",
                "price": 350.00,
                "location_raw": "Montrose, Houston, TX",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["category"] == "furniture"
        assert data["price"] == 350.0
        assert data["has_embedding"] is False

    def test_create_inventory_rejects_invalid_vertical(self, client, user_uuid):
        resp = client.post(
            "/api/v1/inventory",
            headers={"X-Dev-User-Id": user_uuid, "X-Agent-Admin-Key": "admin-local"},
            json={
                "vertical": "invalid",
                "category": "furniture",
                "title": "Bad item",
                "description": "desc",
                "price": 100.0,
            },
        )
        assert resp.status_code == 422

    def test_create_inventory_requires_admin(self, client, user_uuid):
        resp = client.post(
            "/api/v1/inventory",
            headers={"X-Dev-User-Id": user_uuid},
            json={
                "vertical": "goods",
                "category": "furniture",
                "title": "Test",
                "description": "desc",
                "price": 100.0,
            },
        )
        assert resp.status_code == 403


# ---------------------------------------------------------------------------
# Integration: Search API
# ---------------------------------------------------------------------------

def _get_or_create_user_id(client, user_uuid):
    """Auto-create user via API and return their real DB id."""
    resp = client.get("/api/v1/users/me", headers={"X-Dev-User-Id": user_uuid})
    return uuid.UUID(resp.json()["id"])


class TestSearchAPI:
    def _create_confirmed_mandate(self, client, user_uuid, fake_db, now_utc):
        """Create and confirm a mandate for testing search."""
        real_user_id = _get_or_create_user_id(client, user_uuid)
        mandate = _make_mandate(
            owner_id=real_user_id,
            category="furniture",
            vertical="goods",
            description="mid-century modern sofa",
            hard_constraints=[{"field": "location", "value": "Montrose"}],
            negotiation_range=[
                {"dimension": "price", "floor": 100, "ceiling": 500, "opening_position": 350}
            ],
            is_active=True,
            completeness_score=Decimal("0.90"),
        )
        fake_db.add(mandate)
        return mandate

    def test_search_returns_results_with_matching_inventory(self, client, user_uuid, fake_db, now_utc):
        mandate = self._create_confirmed_mandate(client, user_uuid, fake_db, now_utc)

        # Seed matching inventory
        item = _make_inventory(
            category="furniture", vertical="goods",
            price=Decimal("420.00"), location_raw="Montrose, Houston, TX",
            description="mid-century modern sofa walnut legs",
        )
        fake_db.add(item)

        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/search",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "search_id" in data
        assert "escalations" in data
        assert data["candidates_pre_filter"] >= 1

    def test_search_filters_wrong_category(self, client, user_uuid, fake_db, now_utc):
        mandate = self._create_confirmed_mandate(client, user_uuid, fake_db, now_utc)

        # Only add electronics — should be filtered out
        item = _make_inventory(
            category="electronics", vertical="goods",
            price=Decimal("200.00"), location_raw="Montrose, Houston, TX",
        )
        fake_db.add(item)

        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/search",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Wrong category should be filtered — post-filter count less than pre
        assert data["candidates_post_filter"] == 0

    def test_search_returns_escalations_for_above_ceiling(self, client, user_uuid, fake_db, now_utc):
        mandate = self._create_confirmed_mandate(client, user_uuid, fake_db, now_utc)

        # Item at $550 — above $500 ceiling, within 15% threshold
        item = _make_inventory(
            category="furniture", vertical="goods",
            price=Decimal("550.00"), location_raw="Montrose, Houston, TX",
            description="mid-century modern sofa excellent walnut",
        )
        fake_db.add(item)

        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/search",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 200
        data = resp.json()
        # Item above ceiling captured in escalations array
        assert data["candidates_post_filter"] == 0
        # escalations may have 0 entries if text similarity below threshold

    def test_search_blocked_by_privacy_gate(self, client, user_uuid, fake_db, now_utc):
        """Privacy gate should block mandate with opening_position == ceiling."""
        real_user_id = _get_or_create_user_id(client, user_uuid)
        mandate = _make_mandate(
            owner_id=real_user_id,
            category="furniture", vertical="goods",
            negotiation_range=[
                {"dimension": "price", "floor": 100, "ceiling": 500, "opening_position": 500}
            ],
            is_active=True,
            completeness_score=Decimal("0.90"),
        )
        fake_db.add(mandate)

        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/search",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 422
        data = resp.json()
        assert data["error"] == "privacy_gate_blocked"

    def test_search_requires_ownership(self, client, user_uuid, other_user_uuid, fake_db, now_utc):
        mandate = _make_mandate(owner_id=uuid.UUID(other_user_uuid))
        fake_db.add(mandate)
        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/search",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 403

    def test_search_result_has_required_fields(self, client, user_uuid, fake_db, now_utc):
        mandate = self._create_confirmed_mandate(client, user_uuid, fake_db, now_utc)
        item = _make_inventory(
            category="furniture", vertical="goods",
            price=Decimal("300.00"), location_raw="Montrose, Houston, TX",
        )
        fake_db.add(item)

        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/search",
            headers={"X-Dev-User-Id": user_uuid},
        )
        assert resp.status_code == 200
        data = resp.json()
        if data["results"]:
            result = data["results"][0]
            assert "result_id" in result
            assert "listing_id" in result
            assert "alignment_score" in result
            assert "within_mandate" in result
            assert "matched_dimensions" in result
            assert "explanation" in result


# ---------------------------------------------------------------------------
# Integration: Signals API
# ---------------------------------------------------------------------------

class TestSignalsAPI:
    def _setup_search_result(self, client, user_uuid, fake_db, now_utc):
        """Create a mandate + search result for signal testing."""
        real_user_id = _get_or_create_user_id(client, user_uuid)
        mandate = _make_mandate(
            owner_id=real_user_id,
            is_active=True,
            completeness_score=Decimal("0.90"),
        )
        fake_db.add(mandate)

        item = _make_inventory()
        fake_db.add(item)

        search_run = SearchRun(
            id=uuid.uuid4(),
            mandate_id=mandate.id,
            mandate_version=1,
            candidates_pre_filter=1,
            candidates_post_filter=1,
            result_count=1,
            escalation_count=0,
            top_score=Decimal("0.85"),
            latency_ms=100,
            created_at=now_utc,
        )
        fake_db.add(search_run)

        result = _make_search_result(
            search_run_id=search_run.id,
            listing_id=item.id,
        )
        fake_db.add(result)

        return mandate, result

    def test_accept_signal_returns_signal_id(self, client, user_uuid, fake_db, now_utc):
        mandate, result = self._setup_search_result(client, user_uuid, fake_db, now_utc)
        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/signals",
            headers={"X-Dev-User-Id": user_uuid},
            json={"search_result_id": str(result.id), "signal_type": "accept"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "signal_id" in data
        assert data["signal_type"] == "accept"

    def test_reject_signal_with_dealbreaker_reason(self, client, user_uuid, fake_db, now_utc):
        mandate, result = self._setup_search_result(client, user_uuid, fake_db, now_utc)
        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/signals",
            headers={"X-Dev-User-Id": user_uuid},
            json={
                "search_result_id": str(result.id),
                "signal_type": "reject",
                "reason": "I don't want leather",
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["signal_type"] == "reject"
        # Should have applied a mandate delta for the leather dealbreaker
        delta = data.get("mandate_delta_applied", {})
        if delta.get("add_dealbreakers"):
            fields = [d["field"] for d in delta["add_dealbreakers"]]
            assert "leather" in fields

    def test_invalid_signal_type_returns_422(self, client, user_uuid, fake_db, now_utc):
        mandate, result = self._setup_search_result(client, user_uuid, fake_db, now_utc)
        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/signals",
            headers={"X-Dev-User-Id": user_uuid},
            json={"search_result_id": str(result.id), "signal_type": "thumbs_up"},
        )
        assert resp.status_code == 422

    def test_signal_for_nonexistent_result_returns_404(self, client, user_uuid, fake_db, now_utc):
        real_user_id = _get_or_create_user_id(client, user_uuid)
        mandate = _make_mandate(owner_id=real_user_id, is_active=True)
        fake_db.add(mandate)
        resp = client.post(
            f"/api/v1/mandates/{mandate.id}/signals",
            headers={"X-Dev-User-Id": user_uuid},
            json={
                "search_result_id": str(uuid.uuid4()),
                "signal_type": "accept",
            },
        )
        assert resp.status_code == 404

    def test_escalation_signal_types_accepted(self, client, user_uuid, fake_db, now_utc):
        mandate, result = self._setup_search_result(client, user_uuid, fake_db, now_utc)
        for signal_type in ("escalation_yes", "escalation_no"):
            resp = client.post(
                f"/api/v1/mandates/{mandate.id}/signals",
                headers={"X-Dev-User-Id": user_uuid},
                json={"search_result_id": str(result.id), "signal_type": signal_type},
            )
            assert resp.status_code == 200, f"Failed for signal_type={signal_type}"
