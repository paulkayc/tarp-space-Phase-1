"""
Tests for personal agent persona collection (onboarding memory).

Verifies that the Personal Agent correctly extracts and persists personal
profile fields (name, home_city, etc.) — not mandate fields.
"""
from fastapi import status


def test_persona_flow_captures_name_and_city(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert create_response.status_code == status.HTTP_200_OK
    conversation_id = create_response.json()["conversation"]["id"]

    message = "My name is Jordan and I live in Houston. I prefer quick summaries."
    send_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": message},
    )
    assert send_response.status_code == status.HTTP_200_OK
    payload = send_response.json()

    assert payload["persona"].get("name") == "Jordan"
    assert "houston" in str(payload["persona"].get("home_city", "")).lower()
    assert payload["persona"].get("communication_style") == "brief"

    # Persona must NOT contain mandate fields
    for mandate_field in ("intent_type", "vertical", "category", "budget", "condition", "timing"):
        assert mandate_field not in payload["persona"], (
            f"mandate field '{mandate_field}' found in personal agent persona"
        )


def test_persona_flow_history_returns_messages_and_persona(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "My name is Casey and I'm based in Seattle."},
    )

    history_response = client.get(
        f"/api/v1/personal-agent/sessions/{conversation_id}",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert history_response.status_code == status.HTTP_200_OK
    payload = history_response.json()
    assert payload["conversation"]["id"] == conversation_id
    assert payload["total"] >= 2
    assert payload["persona"].get("name") == "Casey"


def test_persona_completeness_progresses(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    # Only name provided — should not be complete yet
    resp1 = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "My name is Riley."},
    )
    assert resp1.json()["elicitation_complete"] is False
    assert resp1.json()["completeness_score"] < 0.7

    # Add city — combined score should increase but still not complete (needs one more)
    resp2 = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I live in Denver."},
    )
    score2 = resp2.json()["completeness_score"]
    assert score2 > resp1.json()["completeness_score"]

    # Add a preference field to cross the 0.70 threshold
    resp3 = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I usually look for furniture and electronics."},
    )
    assert resp3.json()["completeness_score"] >= 0.70
    assert resp3.json()["elicitation_complete"] is True


def test_persona_agent_session_isolation(client, user_uuid, other_user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    forbidden_response = client.get(
        f"/api/v1/personal-agent/sessions/{conversation_id}",
        headers={"X-Dev-User-Id": other_user_uuid},
    )
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
