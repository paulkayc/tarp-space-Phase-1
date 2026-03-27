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
