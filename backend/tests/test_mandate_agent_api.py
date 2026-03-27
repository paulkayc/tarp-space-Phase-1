"""
Tests for the Mandate Agent API.

Verifies mandate elicitation flow, persona memory pre-fill (home_city →
default location), gap-fill loop, and session isolation.
"""
from fastapi import status


def test_mandate_agent_session_create(client, user_uuid):
    response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()

    assert "conversation" in payload
    assert "mandate" in payload
    assert "agent_message" in payload
    assert payload["conversation"]["status"] == "active"
    assert payload["agent_message"]["role"] == "agent"

    # Opening prompt should be about buying/selling/services — not personal profile
    opening = payload["agent_message"]["content"].lower()
    assert any(word in opening for word in ["buy", "sell", "service", "looking", "today"])


def test_mandate_agent_captures_intent_and_category(client, user_uuid):
    create_response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    send_response = client.post(
        f"/api/v1/mandate-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I want to buy a sofa under $600 in good condition."},
    )
    assert send_response.status_code == status.HTTP_200_OK
    turn = send_response.json()

    mandate_state = turn["mandate_state"]
    assert mandate_state.get("intent_type") == "buy"
    assert mandate_state.get("category") == "furniture"
    assert "budget" in mandate_state
    assert mandate_state["budget"].get("max") == 600.0
    assert mandate_state.get("condition") == "good"


def test_mandate_agent_prefills_location_from_persona_memory(client, user_uuid):
    # First save home_city to personal memory
    client.post(
        "/api/v1/personal-agent/memories",
        headers={"X-Dev-User-Id": user_uuid},
        json={
            "content": "home_city: Austin",
            "tags": ["home_city", "persona", "preferences"],
            "source": "explicit",
            "confidence": 1.0,
        },
    )

    # Create a mandate session — it should pre-fill location from home_city
    create_response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert create_response.status_code == status.HTTP_200_OK
    mandate = create_response.json()["mandate"]

    # Location should already be pre-filled from persona home_city
    constraints = mandate.get("hard_constraints", [])
    location_constraints = [c for c in constraints if c.get("field") == "location"]
    assert len(location_constraints) == 1
    assert "austin" in location_constraints[0]["value"].lower()


def test_mandate_agent_gap_questions_are_mandate_specific(client, user_uuid):
    create_response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    send_response = client.post(
        f"/api/v1/mandate-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I want to buy a laptop."},
    )
    assert send_response.status_code == status.HTTP_200_OK
    agent_reply = send_response.json()["agent_message"]["content"].lower()

    # The next gap question should be about mandate fields, not personal profile
    persona_keywords = ["your name", "what city do you live", "communication style"]
    assert not any(kw in agent_reply for kw in persona_keywords), (
        f"Mandate agent asked a persona question: {agent_reply}"
    )


def test_mandate_agent_session_history(client, user_uuid):
    create_response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    client.post(
        f"/api/v1/mandate-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I want to buy a desk in Seattle under $400."},
    )

    history_response = client.get(
        f"/api/v1/mandate-agent/sessions/{conversation_id}",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert history_response.status_code == status.HTTP_200_OK
    payload = history_response.json()
    assert payload["conversation"]["id"] == conversation_id
    assert payload["total"] >= 2


def test_mandate_agent_get_mandate_endpoint(client, user_uuid):
    create_response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    client.post(
        f"/api/v1/mandate-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I need to buy a fridge under $800."},
    )

    mandate_response = client.get(
        f"/api/v1/mandate-agent/sessions/{conversation_id}/mandate",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert mandate_response.status_code == status.HTTP_200_OK
    mandate = mandate_response.json()
    assert mandate["intent_type"] == "buy"
    assert mandate["category"] == "appliance"


def test_mandate_agent_session_isolation(client, user_uuid, other_user_uuid):
    create_response = client.post(
        "/api/v1/mandate-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    forbidden_response = client.get(
        f"/api/v1/mandate-agent/sessions/{conversation_id}",
        headers={"X-Dev-User-Id": other_user_uuid},
    )
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden_response.json() == {
        "error": "forbidden",
        "message": "You do not own this conversation",
    }
