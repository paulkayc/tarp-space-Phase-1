from fastapi import status


def test_personal_agent_session_create_and_history(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert create_response.status_code == status.HTTP_200_OK
    payload = create_response.json()
    conversation_id = payload["conversation"]["id"]
    assert payload["agent_message"]["role"] == "agent"

    history_response = client.get(
        f"/api/v1/personal-agent/sessions/{conversation_id}",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert history_response.status_code == status.HTTP_200_OK
    history = history_response.json()
    assert history["conversation"]["id"] == conversation_id
    assert history["total"] >= 1


def test_personal_agent_send_message_and_memory_question(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    send_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I want to buy a modern sofa in Houston under $900."},
    )
    assert send_response.status_code == status.HTTP_200_OK
    turn = send_response.json()
    assert turn["persona"]["category"] == "furniture"
    assert turn["persona"]["location"] == "Houston"

    memory_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "What do you remember about me?"},
    )
    assert memory_response.status_code == status.HTTP_200_OK
    memory_turn = memory_response.json()
    assert "remember" in memory_turn["agent_message"]["content"].lower()
    assert "category: furniture" in memory_turn["agent_message"]["content"].lower()


def test_personal_agent_session_isolation(client, user_uuid, other_user_uuid):
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
    assert forbidden_response.json() == {
        "error": "forbidden",
        "message": "You do not own this conversation",
    }


def test_personal_agent_memory_crud_and_search(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/memories",
        headers={"X-Dev-User-Id": user_uuid},
        json={
            "content": "prefers modern style furniture",
            "tags": ["style", "persona"],
            "source": "explicit",
            "confidence": 1.0,
        },
    )
    assert create_response.status_code == status.HTTP_200_OK
    memory = create_response.json()
    memory_id = memory["id"]

    search_response = client.get(
        "/api/v1/personal-agent/memories/search",
        headers={"X-Dev-User-Id": user_uuid},
        params={"q": "modern style", "limit": 5},
    )
    assert search_response.status_code == status.HTTP_200_OK
    payload = search_response.json()
    assert payload["count"] >= 1
    assert any("modern style furniture" in item["content"] for item in payload["memories"])

    update_response = client.patch(
        f"/api/v1/personal-agent/memories/{memory_id}",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "prefers mid-century modern style furniture"},
    )
    assert update_response.status_code == status.HTTP_200_OK
    updated = update_response.json()
    assert "mid-century modern" in updated["content"]
