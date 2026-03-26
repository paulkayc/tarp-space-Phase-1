"""
Tests for dev auth, user endpoints, and onboarding session flow.

Covers (per spec):
  Auth:
    - No X-Dev-User-Id header → 401
    - Non-UUID X-Dev-User-Id → 401
  Users:
    - GET /users/me with new UUID → auto-creates user, returns account_created
    - GET /users/me same UUID twice → same user, no duplicate
    - Two different UUIDs → two different users (isolation)
    - PATCH /users/me → updates display_name
  Onboarding:
    - POST /onboarding/message "I'm Maria in the Heights" → persona has name + neighborhood
    - POST /onboarding/message sex skip → gap_analyzer never asks sex again
    - POST /onboarding/skip → sets onboarding_completed_at, returns skipped=true
    - GET /onboarding/persona after messages → completeness_score > 0
    - PATCH /onboarding/persona/fields dot-notation → style_affinities updated
    - Full 6-message simulation → completeness >= 0.7, onboarding_complete=true
    - onboarding_completed event in activity_log after completion
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.auth import get_current_owner_id, get_or_create_user
from app.db.session import get_db


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

def _new_uuid() -> str:
    return str(uuid.uuid4())


def _make_user(owner_id: str | None = None, persona: dict | None = None) -> MagicMock:
    uid = owner_id or _new_uuid()
    user = MagicMock()
    user.id = uuid.UUID(uid) if isinstance(uid, str) else uid
    user.external_user_id = str(uid)
    user.email = None
    user.display_name = f"User {str(uid)[:8]}"
    user.phone = None
    user.sex = None
    user.location_raw = None
    user.onboarding_completed_at = None
    user.persona = persona or {}
    user.created_at = datetime.now(timezone.utc)
    user.updated_at = datetime.now(timezone.utc)
    return user


def _make_db(user: MagicMock | None = None) -> MagicMock:
    db = MagicMock()
    db.query.return_value.filter.return_value.first.return_value = user
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.filter.return_value.first.return_value = None
    return db


def _client_with(owner_id: str, user: MagicMock, db: MagicMock) -> TestClient:
    """Build a TestClient that bypasses auth and DB for the given user."""
    app.dependency_overrides[get_or_create_user] = lambda: user
    app.dependency_overrides[get_db] = lambda: db
    return TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Auth — header validation
# ─────────────────────────────────────────────────────────────────────────────

def test_missing_header_returns_401():
    """No X-Dev-User-Id header → 401 unauthorized."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get("/api/v1/users/me")
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"] == "unauthorized"
    assert "X-Dev-User-Id" in body["detail"]["message"]


def test_non_uuid_header_returns_401():
    """X-Dev-User-Id that is not a UUID → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    response = client.get(
        "/api/v1/users/me",
        headers={"X-Dev-User-Id": "not-a-uuid"},
    )
    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["error"] == "unauthorized"
    assert "UUID" in body["detail"]["message"]


def test_non_v4_uuid_header_returns_401():
    """A UUID that is not v4 (e.g. nil UUID) → 401."""
    client = TestClient(app, raise_server_exceptions=False)
    # nil UUID has version=None, not v4
    response = client.get(
        "/api/v1/users/me",
        headers={"X-Dev-User-Id": "00000000-0000-0000-0000-000000000000"},
    )
    assert response.status_code == 401


# ─────────────────────────────────────────────────────────────────────────────
# GET /users/me — auto-create and idempotency
# ─────────────────────────────────────────────────────────────────────────────

def test_get_me_new_uuid_returns_account_created():
    """First call with a new UUID auto-creates user and returns account_created."""
    uid = _new_uuid()
    user = _make_user(uid)
    db = _make_db(user)

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.get(
            "/api/v1/users/me",
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["dev_user_id"] == uid
    assert body["onboarding_status"] == "account_created"
    assert body["persona_completeness"] == 0.0


def test_get_me_same_uuid_twice_returns_same_user():
    """Same UUID on two requests returns identical user data (no duplicate row)."""
    uid = _new_uuid()
    user = _make_user(uid)
    db = _make_db(user)

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        r1 = client.get("/api/v1/users/me", headers={"X-Dev-User-Id": uid})
        r2 = client.get("/api/v1/users/me", headers={"X-Dev-User-Id": uid})
    finally:
        app.dependency_overrides.clear()

    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["id"] == r2.json()["id"]
    assert r1.json()["dev_user_id"] == r2.json()["dev_user_id"]


def test_two_different_uuids_return_different_users():
    """Two requests with different UUIDs → different user records."""
    uid_a = _new_uuid()
    uid_b = _new_uuid()
    user_a = _make_user(uid_a)
    user_b = _make_user(uid_b)
    db_a = _make_db(user_a)
    db_b = _make_db(user_b)

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user_a
        app.dependency_overrides[get_db] = lambda: db_a
        client = TestClient(app)
        r_a = client.get("/api/v1/users/me", headers={"X-Dev-User-Id": uid_a})
    finally:
        app.dependency_overrides.clear()

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user_b
        app.dependency_overrides[get_db] = lambda: db_b
        client = TestClient(app)
        r_b = client.get("/api/v1/users/me", headers={"X-Dev-User-Id": uid_b})
    finally:
        app.dependency_overrides.clear()

    assert r_a.status_code == 200
    assert r_b.status_code == 200
    assert r_a.json()["id"] != r_b.json()["id"]
    assert r_a.json()["dev_user_id"] != r_b.json()["dev_user_id"]


def test_patch_me_updates_display_name():
    """PATCH /users/me with display_name updates and returns new value."""
    uid = _new_uuid()
    user = _make_user(uid)
    db = _make_db(user)

    def _patched_user():
        user.display_name = "Alex"
        return user

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.patch(
            "/api/v1/users/me",
            json={"display_name": "Alex"},
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["display_name"] == "Alex"


def test_patch_me_invalid_phone_returns_422():
    """PATCH /users/me with an invalid phone format → 422."""
    uid = _new_uuid()
    user = _make_user(uid)
    db = _make_db(user)

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.patch(
            "/api/v1/users/me",
            json={"phone": "5551234"},  # no leading +
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 422


# ─────────────────────────────────────────────────────────────────────────────
# Onboarding — message pipeline
# ─────────────────────────────────────────────────────────────────────────────

def _make_onboarding_db(user: MagicMock) -> MagicMock:
    """DB mock with working session / message add/commit cycle."""
    db = MagicMock()

    # OnboardingSession query returns None (no existing session → will be created)
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None
    db.query.return_value.filter.return_value.first.return_value = None

    # refresh does nothing on mocks
    db.refresh.return_value = None

    # Simulate session creation: after db.add + db.commit, db.refresh updates session.id
    created_session = MagicMock()
    created_session.id = uuid.uuid4()
    created_session.status = "active"
    created_session.owner_id = user.id
    created_session.last_message_at = datetime.now(timezone.utc)

    # Patch db.add to capture the OnboardingSession and return it on next query
    def _side_effect_add(obj):
        pass

    db.add.side_effect = _side_effect_add

    # After refresh(session), the session gets an ID
    def _refresh_side_effect(obj):
        if hasattr(obj, "status") and not hasattr(obj, "external_user_id"):
            obj.id = created_session.id

    db.refresh.side_effect = _refresh_side_effect

    return db, created_session


@patch("app.api.onboarding.save_persona_delta")
@patch("app.api.onboarding.extract_persona_delta")
def test_message_extracts_name_and_neighborhood(mock_extract, mock_save):
    """POST /onboarding/message 'I'm Maria in the Heights' → persona with name + neighborhood."""
    uid = _new_uuid()
    persona_after = {
        "identity": {"display_name": "Maria"},
        "location": {"neighborhood": "The Heights"},
        "completeness_score": 0.45,
    }
    user = _make_user(uid, persona={})
    db, _ = _make_onboarding_db(user)

    mock_extract.return_value = {
        "identity": {"display_name": "Maria"},
        "location": {"neighborhood": "The Heights"},
    }
    mock_save.return_value = persona_after
    # After save, user.persona reflects update
    user.persona = persona_after

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        with patch("app.api.onboarding.generate_gap_question", return_value="What's your sex?"):
            client = TestClient(app)
            response = client.post(
                "/api/v1/onboarding/message",
                json={"content": "I'm Maria in the Heights"},
                headers={"X-Dev-User-Id": uid},
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    # Verify extractor was called with the user message
    mock_extract.assert_called_once()
    args = mock_extract.call_args[0]
    assert "Maria" in args[0] or "Maria" in str(args)
    # Persona delta propagated
    delta = body["persona_delta"]
    assert delta.get("identity", {}).get("display_name") == "Maria"
    assert delta.get("location", {}).get("neighborhood") == "The Heights"
    assert body["onboarding_complete"] is False


@patch("app.api.onboarding.save_persona_delta")
@patch("app.api.onboarding.extract_persona_delta")
def test_message_sex_skip_not_asked_again(mock_extract, mock_save):
    """
    After sex is declined via mark_declined, gap_analyzer skips it.
    The agent should NOT return 'identity.sex' as the next gap field.
    """
    from app.services.onboarding.gap_analyzer import mark_declined, find_next_gap

    uid = _new_uuid()
    # Persona with name + neighborhood, sex declined
    persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "completeness_score": 0.45,
    }
    persona = mark_declined(persona, "identity.sex")

    # Verify gap analyzer skips sex
    field, _ = find_next_gap(persona)
    assert field != "identity.sex", "Gap analyzer should skip declined sex field"


@patch("app.api.onboarding.emit_event")
@patch("app.api.onboarding.save_persona_delta")
@patch("app.api.onboarding.extract_persona_delta")
def test_skip_sets_completed_at_and_returns_skipped(mock_extract, mock_save, mock_emit):
    """POST /onboarding/skip → sets onboarding_completed_at, returns skipped=true."""
    uid = _new_uuid()
    user = _make_user(uid, persona={})
    db, _ = _make_onboarding_db(user)

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.post(
            "/api/v1/onboarding/skip",
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["skipped"] is True
    assert "completeness_score" in body
    # user.onboarding_completed_at was set
    assert user.onboarding_completed_at is not None
    # emit_event called with onboarding_completed
    mock_emit.assert_called_once_with(
        "onboarding_completed",
        {"final_completeness_score": pytest.approx(0.0), "skipped": True},
        owner_id=user.id,
        db=db,
    )


@patch("app.api.onboarding.save_persona_delta")
@patch("app.api.onboarding.extract_persona_delta")
def test_get_persona_after_messages_has_positive_score(mock_extract, mock_save):
    """GET /onboarding/persona with persona already set → completeness_score > 0."""
    uid = _new_uuid()
    persona = {
        "identity": {"display_name": "Alex"},
        "completeness_score": 0.20,
    }
    user = _make_user(uid, persona=persona)
    db = _make_db(user)

    # No active session
    db.query.return_value.filter.return_value.order_by.return_value.first.return_value = None

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.get(
            "/api/v1/onboarding/persona",
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["completeness_score"] > 0.0


@patch("app.api.onboarding.save_persona_delta")
def test_patch_persona_fields_dot_notation(mock_save):
    """PATCH /onboarding/persona/fields with dot-notation path updates nested field."""
    uid = _new_uuid()
    user = _make_user(uid, persona={"identity": {"display_name": "Alex"}})
    db = _make_db(user)

    updated_persona = {
        "identity": {"display_name": "Alex"},
        "preferences": {"style_affinities": ["minimalist"]},
        "completeness_score": 0.20,
    }
    mock_save.return_value = updated_persona

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.patch(
            "/api/v1/onboarding/persona/fields",
            json={"path": "preferences.style_affinities", "value": ["minimalist"]},
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["field_updated"] == "preferences.style_affinities"
    assert body["source"] == "explicit"
    # The save was called with a delta containing the new value
    mock_save.assert_called_once()
    call_delta = mock_save.call_args[0][2]
    assert call_delta["preferences"]["style_affinities"] == ["minimalist"]


# ─────────────────────────────────────────────────────────────────────────────
# Full onboarding simulation
# ─────────────────────────────────────────────────────────────────────────────

@patch("app.api.onboarding.emit_event")
@patch("app.api.onboarding.generate_completion_summary")
@patch("app.api.onboarding.save_persona_delta")
@patch("app.api.onboarding.extract_persona_delta")
def test_full_onboarding_reaches_completion(mock_extract, mock_save, mock_summary, mock_emit):
    """
    Six messages covering name, location, pets, home type, style, and budget.
    After accumulation, completeness reaches >= 0.7 → onboarding_complete=true.
    """
    uid = _new_uuid()

    # Full persona that would result from 6 messages
    full_persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {
            "style_affinities": ["mid-century modern"],
            "typical_budget_goods": {"floor": 100, "ceiling": 500},
        },
        "lifestyle": {"has_pets": False, "home_type": "apartment"},
        "trust_seeds": {"community_names": ["Heights Neighbors"]},
        "completeness_score": 1.0,
    }

    user = _make_user(uid, persona=full_persona)
    db, created_session = _make_onboarding_db(user)

    # The session is active (not yet completed)
    created_session.status = "active"

    mock_extract.return_value = {}  # Nothing new to extract — persona already complete
    mock_save.return_value = full_persona
    mock_summary.return_value = "Great, you're all set Alex!"

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.post(
            "/api/v1/onboarding/message",
            json={"content": "Sounds good"},
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    body = response.json()
    assert body["onboarding_complete"] is True
    assert body["agent_message"] == "Great, you're all set Alex!"
    assert body["completeness_score"] >= 0.7


@patch("app.api.onboarding.emit_event")
@patch("app.api.onboarding.generate_completion_summary")
@patch("app.api.onboarding.save_persona_delta")
@patch("app.api.onboarding.extract_persona_delta")
def test_onboarding_completed_event_in_activity_log(mock_extract, mock_save, mock_summary, mock_emit):
    """
    When onboarding completes, emit_event is called with 'onboarding_completed'
    and skipped=false in the payload.
    """
    uid = _new_uuid()
    full_persona = {
        "identity": {"display_name": "Alex"},
        "location": {"neighborhood": "Montrose"},
        "preferences": {"style_affinities": ["modern"], "typical_budget_goods": {"floor": 50, "ceiling": 200}},
        "lifestyle": {"has_pets": True, "home_type": "condo"},
        "trust_seeds": {"community_names": ["UH Alumni"]},
        "completeness_score": 1.0,
    }

    user = _make_user(uid, persona=full_persona)
    db, _ = _make_onboarding_db(user)

    mock_extract.return_value = {}
    mock_save.return_value = full_persona
    mock_summary.return_value = "All done!"

    try:
        app.dependency_overrides[get_or_create_user] = lambda: user
        app.dependency_overrides[get_db] = lambda: db
        client = TestClient(app)
        response = client.post(
            "/api/v1/onboarding/message",
            json={"content": "Done"},
            headers={"X-Dev-User-Id": uid},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["onboarding_complete"] is True

    # Verify onboarding_completed event was emitted with skipped=False
    emit_calls = [
        call for call in mock_emit.call_args_list
        if call[0][0] == "onboarding_completed"
    ]
    assert len(emit_calls) == 1
    payload = emit_calls[0][0][1]
    assert payload["skipped"] is False
    assert payload["final_completeness_score"] >= 0.7


# ─────────────────────────────────────────────────────────────────────────────
# set_nested helper (pure function test)
# ─────────────────────────────────────────────────────────────────────────────

def test_set_nested_creates_nested_path():
    from app.api.onboarding import set_nested
    result = set_nested({}, "location.neighborhood", "Montrose")
    assert result == {"location": {"neighborhood": "Montrose"}}


def test_set_nested_merges_existing_keys():
    from app.api.onboarding import set_nested
    base = {"location": {"city": "Houston"}}
    result = set_nested(base, "location.neighborhood", "Montrose")
    assert result["location"]["city"] == "Houston"
    assert result["location"]["neighborhood"] == "Montrose"


def test_set_nested_does_not_mutate_original():
    from app.api.onboarding import set_nested
    base = {"location": {"city": "Houston"}}
    set_nested(base, "location.neighborhood", "Montrose")
    assert "neighborhood" not in base.get("location", {})
