"""
Onboarding agent tests.

Covers (per spec):
  Extractor:
    - "I'm Maria, I live in the Heights" → display_name + neighborhood
    - "I have two cats" → lifestyle.has_pets=true
  Gap analyzer:
    - Returns display_name question when persona is empty
    - Skips neighborhood when location already set
    - Returns None when completeness >= 0.7
    - Never asks sex or phone again after source="declined"
  Persona-to-mandate:
    - has_pets=true → pet_friendly soft_preference on goods mandate
    - Does NOT overwrite an existing explicit mandate field
    - typical_budget_goods applies to goods, not services
  Completeness score:
    - identity only → 0.20
    - identity + location → 0.45
  Onboarding endpoint:
    - skip sets onboarding_completed_at
  Persona PATCH:
    - dot-notation update of nested field works
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.onboarding.extractor import extract_persona_delta
from app.services.onboarding.gap_analyzer import (
    compute_completeness_score,
    find_next_gap,
    mark_declined,
)
from app.services.onboarding.persona_to_mandate import prefill_mandate_from_persona


# ─────────────────────────────────────────────────────────────────────────────
# Extractor
# ─────────────────────────────────────────────────────────────────────────────

def _make_anthropic_response(text: str) -> MagicMock:
    """Build a mock Anthropic response with a single text content block."""
    content_block = MagicMock()
    content_block.text = text
    response = MagicMock()
    response.content = [content_block]
    return response


@patch("app.services.onboarding.extractor.anthropic.Anthropic")
def test_extractor_name_and_neighborhood(mock_anthropic_cls):
    """'I'm Maria, I live in the Heights' → display_name + neighborhood."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_anthropic_response(
        json.dumps(
            {
                "identity": {"display_name": "Maria"},
                "location": {"neighborhood": "The Heights"},
            }
        )
    )

    result = extract_persona_delta("I'm Maria, I live in the Heights", {})

    assert result["identity"]["display_name"] == "Maria"
    assert result["location"]["neighborhood"] == "The Heights"


@patch("app.services.onboarding.extractor.anthropic.Anthropic")
def test_extractor_has_pets(mock_anthropic_cls):
    """'I have two cats' → lifestyle.has_pets=true."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_anthropic_response(
        json.dumps({"lifestyle": {"has_pets": True}})
    )

    result = extract_persona_delta("I have two cats", {})

    assert result["lifestyle"]["has_pets"] is True


@patch("app.services.onboarding.extractor.anthropic.Anthropic")
def test_extractor_bad_json_returns_empty(mock_anthropic_cls):
    """Invalid JSON from LLM → returns empty dict (no crash)."""
    mock_client = MagicMock()
    mock_anthropic_cls.return_value = mock_client
    mock_client.messages.create.return_value = _make_anthropic_response("not json at all")

    result = extract_persona_delta("something", {})
    assert result == {}


# ─────────────────────────────────────────────────────────────────────────────
# Completeness score
# ─────────────────────────────────────────────────────────────────────────────

def test_completeness_empty():
    assert compute_completeness_score({}) == 0.0


def test_completeness_identity_only():
    """Only display_name set → 0.20."""
    persona = {"identity": {"display_name": "Alex"}}
    assert compute_completeness_score(persona) == pytest.approx(0.20)


def test_completeness_identity_plus_location():
    """display_name + neighborhood → 0.20 + 0.25 = 0.45."""
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
    }
    assert compute_completeness_score(persona) == pytest.approx(0.45)


def test_completeness_full_profile():
    """All sections filled → 1.0."""
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["mid-century modern"]},
        "lifestyle": {"has_pets": True, "home_type": "apartment"},
        "trust_seeds": {"community_names": ["Heights Neighbors"]},
    }
    assert compute_completeness_score(persona) == pytest.approx(1.0)


def test_completeness_has_pets_false_counts():
    """has_pets=False is a valid filled value (boolean False ≠ missing)."""
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["minimalist"]},
        "lifestyle": {"has_pets": False, "home_type": "condo"},
        "trust_seeds": {"community_names": ["Rice Alumni"]},
    }
    assert compute_completeness_score(persona) == pytest.approx(1.0)


# ─────────────────────────────────────────────────────────────────────────────
# Gap analyzer
# ─────────────────────────────────────────────────────────────────────────────

def test_gap_empty_persona_asks_display_name():
    """Empty persona → ask for display_name first (priority 1)."""
    field, question = find_next_gap({})
    assert field == "identity.display_name"
    assert question  # non-empty question text


def test_gap_skips_filled_location():
    """When location is already set, gap analyzer moves past neighborhood."""
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
    }
    field, _ = find_next_gap(persona)
    # display_name and neighborhood are filled → next is sex (priority 3)
    assert field == "identity.sex"


def test_gap_returns_none_when_complete():
    """completeness >= 0.7 → (None, None)."""
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["minimalist"]},
        "lifestyle": {"has_pets": False, "home_type": "apartment"},
        "trust_seeds": {"community_names": ["Heights Neighbors"]},
    }
    assert compute_completeness_score(persona) >= 0.7
    field, question = find_next_gap(persona)
    assert field is None
    assert question is None


def test_gap_skips_declined_sex():
    """After sex is declined, gap analyzer skips it and moves to has_pets."""
    persona = {"identity": {"display_name": "Alex"}, "location": {"neighborhood": "Montrose"}}
    persona = mark_declined(persona, "identity.sex")
    field, _ = find_next_gap(persona)
    # sex is declined, so next should be has_pets (priority 4)
    assert field == "lifestyle.has_pets"


def test_gap_skips_declined_phone():
    """After phone is declined it is never returned again."""
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["modern"]},
        "lifestyle": {"has_pets": True, "home_type": "house"},
        "trust_seeds": {"community_names": ["UH Alumni"]},
    }
    # All fields filled except phone
    persona = mark_declined(persona, "identity.phone")
    field, _ = find_next_gap(persona)
    # completeness is 1.0, so should be None anyway
    assert field is None


def test_gap_never_asks_about_already_filled_field():
    """Gap analyzer never returns a field that is already present."""
    full_persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["minimalist"]},
        "lifestyle": {"has_pets": False, "home_type": "apartment"},
        "trust_seeds": {"community_names": ["Heights Neighbors"]},
    }
    field, _ = find_next_gap(full_persona)
    assert field is None  # fully complete


# ─────────────────────────────────────────────────────────────────────────────
# Persona → Mandate pre-fill
# ─────────────────────────────────────────────────────────────────────────────

def test_persona_to_mandate_has_pets_adds_pet_friendly():
    """has_pets=true → pet_friendly soft_preference added to goods mandate."""
    persona = {
        "lifestyle": {"has_pets": True, "home_type": "apartment"},
    }
    delta = prefill_mandate_from_persona(persona, vertical="goods")

    pet_prefs = [p for p in delta.soft_preferences if p["attribute"] == "pet_friendly"]
    assert len(pet_prefs) == 1
    assert pet_prefs[0]["value"] is True
    assert pet_prefs[0]["source"] == "persona"
    assert "soft_preferences.pet_friendly" in delta.fields_applied


def test_persona_to_mandate_has_pets_ignored_for_services():
    """has_pets is irrelevant for services mandates — should not be added."""
    persona = {"lifestyle": {"has_pets": True}}
    delta = prefill_mandate_from_persona(persona, vertical="services")

    pet_prefs = [p for p in delta.soft_preferences if p["attribute"] == "pet_friendly"]
    assert len(pet_prefs) == 0


def test_persona_to_mandate_no_overwrite_explicit():
    """Does NOT overwrite a field that is already source=explicit in mandate."""
    persona = {
        "location": {"neighborhood": "Montrose", "city": "Houston", "state": "TX"},
    }
    existing_mandate = {"source_flags": {"location": "explicit"}}
    delta = prefill_mandate_from_persona(persona, existing_mandate=existing_mandate)

    assert delta.location is None
    assert "location" not in delta.fields_applied


def test_persona_to_mandate_budget_goods_applies_to_goods():
    """typical_budget_goods → negotiation_range on goods mandate."""
    persona = {
        "preferences": {"typical_budget_goods": {"floor": 100, "ceiling": 500}},
    }
    delta = prefill_mandate_from_persona(persona, vertical="goods")

    assert delta.negotiation_range_floor == 100
    assert delta.negotiation_range_ceiling == 500
    assert "negotiation_range" in delta.fields_applied


def test_persona_to_mandate_budget_goods_not_applied_to_services():
    """typical_budget_goods is ignored when vertical=services."""
    persona = {
        "preferences": {"typical_budget_goods": {"floor": 100, "ceiling": 500}},
    }
    delta = prefill_mandate_from_persona(persona, vertical="services")

    assert delta.negotiation_range_floor is None
    assert delta.negotiation_range_ceiling is None
    assert "negotiation_range" not in delta.fields_applied


def test_persona_to_mandate_style_preferences():
    """style_affinities → soft_preferences with attribute='style'."""
    persona = {
        "preferences": {"style_affinities": ["mid-century modern", "minimalist"]},
    }
    delta = prefill_mandate_from_persona(persona, vertical="goods")

    styles = [p["value"] for p in delta.soft_preferences if p["attribute"] == "style"]
    assert "mid-century modern" in styles
    assert "minimalist" in styles
    for pref in delta.soft_preferences:
        if pref["attribute"] == "style":
            assert pref["source"] == "persona"
            assert pref["weight"] == 0.7


def test_persona_to_mandate_empty_is_empty():
    """Empty persona → empty MandateDelta."""
    delta = prefill_mandate_from_persona({})
    assert delta.is_empty()


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding endpoint (FastAPI TestClient with mocked dependencies)
# ─────────────────────────────────────────────────────────────────────────────

def _make_mock_user(
    completed_at=None,
    persona=None,
) -> MagicMock:
    user = MagicMock()
    user.id = "00000000-0000-0000-0000-000000000001"
    user.external_user_id = "dev-user-1"
    user.onboarding_completed_at = completed_at
    user.persona = persona or {}
    user.updated_at = datetime.now(timezone.utc)
    return user


def test_skip_sets_completed_at():
    """POST /onboarding/skip → sets onboarding_completed_at and returns skipped=true."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_or_create_user
    from app.db.session import get_db

    mock_user = _make_mock_user()
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_or_create_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    client = TestClient(app)
    response = client.post("/api/v1/onboarding/skip")

    assert response.status_code == 200
    body = response.json()
    assert body["skipped"] is True
    assert "completeness_score" in body
    # Verify completed_at was set on the user object
    assert mock_user.onboarding_completed_at is not None

    app.dependency_overrides.clear()


def test_persona_patch_dot_notation():
    """PATCH /onboarding/persona/fields with dot-notation path updates nested field."""
    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_or_create_user
    from app.db.session import get_db

    mock_user = _make_mock_user(persona={"identity": {"display_name": "Alex"}})
    mock_user.external_user_id = "00000000-0000-0000-0000-000000000001"
    mock_db = MagicMock()
    mock_db.query.return_value.filter.return_value.first.return_value = mock_user

    # Make save_persona_delta return a plausible updated persona
    saved_persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "The Heights"},
        "completeness_score": 0.45,
        "collected_at": datetime.now(timezone.utc).isoformat(),
    }

    app.dependency_overrides[get_or_create_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    with patch(
        "app.api.onboarding.save_persona_delta", return_value=saved_persona
    ):
        client = TestClient(app)
        response = client.patch(
            "/api/v1/onboarding/persona/fields",
            json={"path": "location.neighborhood", "value": "The Heights"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["field_updated"] == "location.neighborhood"
    assert body["source"] == "explicit"
    assert body["completeness_score"] == pytest.approx(0.45)

    app.dependency_overrides.clear()


def test_full_onboarding_flow_reaches_completion():
    """
    Five message exchanges that produce enough completeness to reach >= 0.7.
    Verifies onboarding_completed_at is set when threshold is reached.
    """
    # Build a persona that is already at completeness >= 0.7 so the endpoint
    # takes the completion branch (simulates accumulated state after 5 turns).
    complete_persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["mid-century modern"]},
        "lifestyle": {"has_pets": False, "home_type": "apartment"},
        "trust_seeds": {"community_names": ["Heights Neighbors"]},
        "completeness_score": 1.0,
    }

    from fastapi.testclient import TestClient
    from app.main import app
    from app.core.auth import get_or_create_user
    from app.db.session import get_db

    mock_user = _make_mock_user(persona=complete_persona)
    mock_user.external_user_id = "00000000-0000-0000-0000-000000000001"
    mock_db = MagicMock()
    # Active session query returns None → new session created
    mock_db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    mock_db.query.return_value.filter.return_value.first.return_value = None

    app.dependency_overrides[get_or_create_user] = lambda: mock_user
    app.dependency_overrides[get_db] = lambda: mock_db

    # Extractor returns empty (all fields filled), reflector returns summary
    with (
        patch("app.api.onboarding.extract_persona_delta", return_value={}),
        patch(
            "app.api.onboarding.generate_completion_summary",
            return_value="Great, you're all set!",
        ),
        patch("app.api.onboarding.emit_event"),
    ):
        client = TestClient(app)
        response = client.post(
            "/api/v1/onboarding/message",
            json={"content": "Sounds good"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_complete"] is True
    assert body["agent_message"] == "Great, you're all set!"
    # onboarding_completed_at was set
    assert mock_user.onboarding_completed_at is not None

    app.dependency_overrides.clear()
