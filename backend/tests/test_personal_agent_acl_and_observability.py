from fastapi import status

from app.observability.events import emit_memory_event, emit_personal_agent_turn_event, emit_tool_event


def test_admin_tool_reload_requires_acl(client):
    denied = client.post("/api/v1/personal-agent/admin/tools/reload")
    assert denied.status_code == status.HTTP_403_FORBIDDEN
    assert denied.json() == {
        "error": "forbidden",
        "message": "Agent admin privileges required",
    }


def test_admin_tool_reload_with_valid_key(client):
    allowed = client.post(
        "/api/v1/personal-agent/admin/tools/reload",
        headers={"X-Agent-Admin-Key": "admin-local"},
    )
    assert allowed.status_code == status.HTTP_200_OK
    payload = allowed.json()
    assert payload["reloaded"] is True
    assert payload["count"] >= 3


def test_personal_agent_turn_contains_no_mandate_fields(client, user_uuid):
    """Personal Agent turns must never expose mandate-level fields."""
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    send_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "My name is Alex. I live in Chicago."},
    )
    assert send_response.status_code == status.HTTP_200_OK
    turn = send_response.json()

    # mandate_delta must be absent from personal agent responses
    assert "mandate_delta" not in turn

    # user.persona must only contain personal profile fields
    mandate_fields = {"intent_type", "vertical", "category", "budget", "condition", "timing", "style_preferences", "dealbreakers"}
    persona_keys = set(turn.get("persona", {}).keys())
    overlap = persona_keys & mandate_fields
    assert not overlap, f"Mandate fields found in persona: {overlap}"


def test_observability_helpers_return_structured_payloads():
    turn = emit_personal_agent_turn_event("owner-1", "conversation-1", "started")
    memory = emit_memory_event("owner-1", "memory-1", "created")
    tool = emit_tool_event("owner-1", "memory_search", "completed")

    assert turn["event"] == "personal_agent_turn"
    assert memory["event"] == "personal_memory_event"
    assert tool["event"] == "personal_agent_tool_event"
    assert "timestamp" in turn
    assert "timestamp" in memory
    assert "timestamp" in tool
