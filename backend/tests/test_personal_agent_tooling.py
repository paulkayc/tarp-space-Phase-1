from fastapi import status


def test_personal_agent_tools_endpoint_lists_builtin_tools(client, user_uuid):
    response = client.get(
        "/api/v1/personal-agent/tools",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["count"] >= 3
    names = {tool["name"] for tool in payload["tools"]}
    assert {"memory_add", "memory_search", "memory_update"}.issubset(names)


def test_personal_agent_memory_question_uses_tool_backed_memory(client, user_uuid):
    session_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = session_response.json()["conversation"]["id"]

    client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I want to buy a couch in Houston under $700."},
    )

    memory_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "What do you remember about me?"},
    )
    assert memory_response.status_code == status.HTTP_200_OK
    payload = memory_response.json()
    assert "remember from memory" in payload["agent_message"]["content"].lower()
