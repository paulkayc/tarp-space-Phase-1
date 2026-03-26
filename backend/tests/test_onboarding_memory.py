from fastapi import status


def test_conversation_flow_persists_persona_and_completes(client, user_uuid):
    create_response = client.post(
        "/api/v1/conversations",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert create_response.status_code == status.HTTP_200_OK
    conversation_id = create_response.json()["conversation"]["id"]

    message = (
        "I want to buy a sofa in Houston between $400 and $600 in excellent condition "
        "within 2 weeks. I like mid-century style and no leather."
    )
    send_response = client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": message},
    )
    assert send_response.status_code == status.HTTP_200_OK
    payload = send_response.json()

    assert payload["elicitation_complete"] is True
    assert payload["conversation"]["status"] == "completed"
    assert payload["persona"]["intent_type"] == "buy"
    assert payload["persona"]["category"] == "furniture"
    assert payload["persona"]["location"] == "Houston"
    assert payload["persona"]["budget"]["min"] == 400.0
    assert payload["persona"]["budget"]["max"] == 600.0
    assert "mid-century" in payload["persona"]["style_preferences"]
    assert "leather" in payload["persona"]["dealbreakers"]
    assert payload["completeness_score"] >= 0.7


def test_conversation_history_returns_messages_and_persona(client, user_uuid):
    create_response = client.post(
        "/api/v1/conversations",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={"content": "I need to buy a sofa in Austin under $700."},
    )

    history_response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert history_response.status_code == status.HTTP_200_OK
    payload = history_response.json()
    assert payload["conversation"]["id"] == conversation_id
    assert payload["total"] >= 2
    assert payload["persona"]["intent_type"] == "buy"


def test_conversation_isolation_for_other_user(client, user_uuid, other_user_uuid):
    create_response = client.post(
        "/api/v1/conversations",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    forbidden_response = client.get(
        f"/api/v1/conversations/{conversation_id}",
        headers={"X-Dev-User-Id": other_user_uuid},
    )
    assert forbidden_response.status_code == status.HTTP_403_FORBIDDEN
    assert forbidden_response.json() == {
        "error": "forbidden",
        "message": "You do not own this conversation",
    }


def test_mandate_prefills_from_persona_memory_and_can_confirm(client, user_uuid):
    create_response = client.post(
        "/api/v1/conversations",
        headers={"X-Dev-User-Id": user_uuid},
    )
    conversation_id = create_response.json()["conversation"]["id"]

    client.post(
        f"/api/v1/conversations/{conversation_id}/messages",
        headers={"X-Dev-User-Id": user_uuid},
        json={
            "content": (
                "I want to buy a sofa in Houston between $500 and $900 in good condition "
                "within 1 month. I like modern style and no leather."
            )
        },
    )

    create_mandate_response = client.post(
        "/api/v1/mandates",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert create_mandate_response.status_code == status.HTTP_201_CREATED
    mandate = create_mandate_response.json()

    assert mandate["intent_type"] == "buy"
    assert mandate["vertical"] == "goods"
    assert mandate["category"] == "furniture"
    assert mandate["completeness_score"] >= 0.7

    confirm_response = client.post(
        f"/api/v1/mandates/{mandate['id']}/confirm",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert confirm_response.status_code == status.HTTP_200_OK
    confirmed = confirm_response.json()
    assert confirmed["status"] == "confirmed"
    assert confirmed["confirmed_at"] is not None
