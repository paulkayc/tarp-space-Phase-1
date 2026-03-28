from fastapi import status


def _sample_graph():
    return {
        "nodes": [
            {"id": "start-1", "type": "start", "name": "Start", "config": {}},
            {"id": "guardrail-1", "type": "guardrail", "name": "Input Guardrail", "config": {}},
            {"id": "agent-1", "type": "agent", "name": "Commerce Agent", "config": {}},
            {"id": "end-1", "type": "end", "name": "End", "config": {}},
        ],
        "edges": [
            {"source": "start-1", "target": "guardrail-1"},
            {"source": "guardrail-1", "target": "agent-1"},
            {"source": "agent-1", "target": "end-1"},
        ],
    }


def test_agent_builder_full_lifecycle(client, user_uuid):
    create_project_response = client.post(
        "/api/v1/agent-builder/projects",
        headers={"X-Dev-User-Id": user_uuid},
        json={"name": "Commerce Router", "description": "visual flow"},
    )
    assert create_project_response.status_code == status.HTTP_200_OK
    project = create_project_response.json()
    assert project["status"] == "draft"

    create_version_response = client.post(
        f"/api/v1/agent-builder/projects/{project['id']}/versions",
        headers={"X-Dev-User-Id": user_uuid},
        json={"graph": _sample_graph(), "notes": "first version"},
    )
    assert create_version_response.status_code == status.HTTP_200_OK
    version = create_version_response.json()

    validate_response = client.post(
        f"/api/v1/agent-builder/versions/{version['id']}/validate",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert validate_response.status_code == status.HTTP_200_OK
    assert validate_response.json()["valid"] is True

    simulate_response = client.post(
        f"/api/v1/agent-builder/versions/{version['id']}/simulate",
        headers={"X-Dev-User-Id": user_uuid},
        json={"input_text": "find me office tarps"},
    )
    assert simulate_response.status_code == status.HTTP_200_OK
    simulate_payload = simulate_response.json()
    assert simulate_payload["status"] == "completed"
    assert simulate_payload["output"]["nodes_executed"] == 4

    generate_response = client.post(
        f"/api/v1/agent-builder/versions/{version['id']}/generate",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert generate_response.status_code == status.HTTP_200_OK
    generated_payload = generate_response.json()
    assert generated_payload["artifact_hash"].startswith("v1")
    assert len(generated_payload["files"]) >= 2

    import_response = client.post(
        f"/api/v1/agent-builder/versions/{version['id']}/import",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert import_response.status_code == status.HTTP_200_OK
    assert import_response.json()["imported"] is True

    publish_response = client.post(
        f"/api/v1/agent-builder/versions/{version['id']}/publish",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert publish_response.status_code == status.HTTP_200_OK
    assert publish_response.json()["published"] is True


def test_agent_builder_prevents_invalid_publish(client, user_uuid):
    create_project_response = client.post(
        "/api/v1/agent-builder/projects",
        headers={"X-Dev-User-Id": user_uuid},
        json={"name": "Bad Graph", "description": "missing end"},
    )
    project = create_project_response.json()

    invalid_graph = {
        "nodes": [
            {"id": "start-1", "type": "start", "name": "Start", "config": {}},
            {"id": "agent-1", "type": "agent", "name": "Work", "config": {}},
        ],
        "edges": [{"source": "start-1", "target": "agent-1"}],
    }

    create_version_response = client.post(
        f"/api/v1/agent-builder/projects/{project['id']}/versions",
        headers={"X-Dev-User-Id": user_uuid},
        json={"graph": invalid_graph},
    )
    version_id = create_version_response.json()["id"]

    publish_response = client.post(
        f"/api/v1/agent-builder/versions/{version_id}/publish",
        headers={"X-Dev-User-Id": user_uuid},
    )
    assert publish_response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert publish_response.json()["error"] == "validation_failed"
