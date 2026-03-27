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
    # Opening prompt should be about getting to know the user, not about buying/selling
    opening = payload["agent_message"]["content"].lower()
    assert any(word in opening for word in ["name", "based", "know you", "personal"])

    history_response = client.get(
        f"/api/v1/personal-agent/sessions/{conversation_id}",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert history_response.status_code == status.HTTP_200_OK
    history = history_response.json()
    assert history["conversation"]["id"] == conversation_id
    assert history["total"] >= 1


def test_personal_agent_captures_name_and_city(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    send_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "My name is Alex and I live in Houston."},
    )
    assert send_response.status_code == status.HTTP_200_OK
    turn = send_response.json()

    # Persona fields should reflect personal profile, not mandate fields
    assert turn["persona"].get("name") == "Alex"
    assert "houston" in str(turn["persona"].get("home_city", "")).lower()

    # The response must NOT contain mandate-style fields
    assert "intent_type" not in turn["persona"]
    assert "category" not in turn["persona"]
    assert "budget" not in turn["persona"]

    # mandate_delta must NOT appear in the response
    assert "mandate_delta" not in turn


def test_personal_agent_does_not_ask_mandate_questions(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    send_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "My name is Sam."},
    )
    assert send_response.status_code == status.HTTP_200_OK
    agent_reply = send_response.json()["agent_message"]["content"].lower()

    # Personal agent should NOT ask mandate questions
    mandate_keywords = ["buy", "sell", "category", "budget", "condition", "timing", "service"]
    assert not any(kw in agent_reply for kw in mandate_keywords), (
        f"Personal agent asked a mandate question: {agent_reply}"
    )


def test_personal_agent_memory_question(client, user_uuid):
    create_response = client.post(
        "/api/v1/personal-agent/sessions",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    # First teach the agent something
    client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "My name is Jordan and I live in Austin."},
    )

    # Then ask what it remembers
    memory_response = client.post(
        f"/api/v1/personal-agent/sessions/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "What do you remember about me?"},
    )
    assert memory_response.status_code == status.HTTP_200_OK
    memory_turn = memory_response.json()
    content = memory_turn["agent_message"]["content"].lower()
    assert "remember" in content


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
            "content": "prefers concise updates",
            "tags": ["communication_style", "persona"],
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
        params={"q": "concise updates", "limit": 5},
    )
    assert search_response.status_code == status.HTTP_200_OK
    payload = search_response.json()
    assert payload["count"] >= 1
    assert any("concise updates" in item["content"] for item in payload["memories"])

    update_response = client.patch(
        f"/api/v1/personal-agent/memories/{memory_id}",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "prefers brief bullet-point summaries"},
    )
    assert update_response.status_code == status.HTTP_200_OK
    updated = update_response.json()
    assert "brief" in updated["content"]

    list_response = client.get(
        "/api/v1/personal-agent/memories",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert list_response.status_code == status.HTTP_200_OK
    listed = list_response.json()
    assert listed["count"] >= 1
    assert any(item["id"] == memory_id for item in listed["memories"])
