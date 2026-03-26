from fastapi import status


def test_missing_dev_user_header_returns_401(client):
    response = client.get("/api/v1/users/me")

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "unauthorized",
        "message": "X-Dev-User-Id header required",
    }


def test_non_uuid_dev_user_header_returns_401(client):
    response = client.get(
        "/api/v1/users/me",
        headers={"X-Dev-User-Id": "not-a-uuid"},
    )

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "unauthorized",
        "message": "X-Dev-User-Id must be a valid UUID",
    }


def test_get_users_me_auto_creates_user(client, user_uuid):
    response = client.get(
        "/api/v1/users/me",
        headers={"X-Dev-User-Id": user_uuid},
    )

    assert response.status_code == status.HTTP_200_OK
    payload = response.json()
    assert payload["id"]
    assert payload["dev_user_id"] == user_uuid
    assert payload["onboarding_status"] == "account_created"


def test_get_mandate_with_different_owner_returns_403(client, user_uuid, other_user_uuid):
    create_response = client.post(
        "/api/v1/mandates",
        headers={"X-Dev-User-Id": user_uuid},
    )
    mandate_id = create_response.json()["id"]

    fetch_response = client.get(
        f"/api/v1/mandates/{mandate_id}",
        headers={"X-Dev-User-Id": other_user_uuid},
    )

    assert fetch_response.status_code == status.HTTP_403_FORBIDDEN
    assert fetch_response.json() == {
        "error": "forbidden",
        "message": "You do not own this mandate",
    }


def test_post_mandates_scopes_owner_to_requesting_header(client, user_uuid):
    user_response = client.get(
        "/api/v1/users/me",
        headers={"X-Dev-User-Id": user_uuid},
    )
    owner_id = user_response.json()["id"]

    create_response = client.post(
        "/api/v1/mandates",
        headers={"X-Dev-User-Id": user_uuid},
    )

    assert create_response.status_code == status.HTTP_201_CREATED
    payload = create_response.json()
    assert payload["owner_id"] == owner_id
    assert payload["status"] == "draft"
    assert payload["version"] == 1
    assert payload["completeness_score"] == 0.0
