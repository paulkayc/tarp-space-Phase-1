import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


class FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model
        self._filters: dict = {}

    def filter_by(self, **kwargs):
        self._filters = kwargs
        return self

    def order_by(self, *_args):
        return self

    def all(self):
        items = list(self._session._data.get(self._model, []))
        for key, value in self._filters.items():
            items = [item for item in items if getattr(item, key, None) == value]
        return items

    def first(self):
        results = self.all()
        return results[0] if results else None


class FakeSession:
    def __init__(self):
        self._data = {}

    def query(self, model):
        return FakeQuery(self, model)

    def add(self, obj):
        if getattr(obj, "id", None) is None:
            obj.id = uuid.uuid4()
        self._data.setdefault(type(obj), []).append(obj)

    def commit(self):
        return None

    def refresh(self, _obj):
        return None

    def rollback(self):
        return None

    def close(self):
        return None


# ---------------------------------------------------------------------------
# Anthropic client mock
#
# Intercepts calls to app.services.llm.client.get_llm_client() and returns a
# mock that uses the regex fallback extractors to produce realistic tool_use
# responses.  This keeps all existing test assertions passing without a live
# Anthropic API key.
# ---------------------------------------------------------------------------

class _MockUsage:
    input_tokens = 10
    output_tokens = 10


class _MockToolUseBlock:
    def __init__(self, name: str, input_dict: dict):
        self.type = "tool_use"
        self.name = name
        self.input = input_dict


class _MockTextBlock:
    def __init__(self, text: str):
        self.type = "text"
        self.text = text


class _MockMessage:
    def __init__(self, content: list, stop_reason: str = "end_turn"):
        self.content = content
        self.stop_reason = stop_reason
        self.usage = _MockUsage()


def _build_mock_anthropic_client() -> MagicMock:
    """Return a mock Anthropic client whose messages.create() simulates extraction."""
    # Import fallback extractors lazily to avoid circular imports at module load.
    from app.services.conversation.extractor import (
        _fallback_extract_persona_delta,
        _fallback_extract_mandate_delta,
    )

    def _fake_create(**kwargs):
        tools = kwargs.get("tools", [])
        messages = kwargs.get("messages", [])

        # Find the last user message content
        user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                content = msg.get("content", "")
                if isinstance(content, str):
                    user_content = content
                break

        if tools:
            tool_name = tools[0]["name"]

            if tool_name == "extract_persona_fields":
                delta = _fallback_extract_persona_delta(user_content)
                return _MockMessage(
                    content=[_MockToolUseBlock("extract_persona_fields", delta)],
                    stop_reason="tool_use",
                )

            if tool_name == "extract_mandate_fields":
                raw = _fallback_extract_mandate_delta(user_content)
                # Flatten negotiation_range → budget_min / budget_max
                flat: dict = {}
                for key in ("intent_type", "vertical", "category"):
                    if key in raw:
                        flat[key] = raw[key]
                nr = raw.get("negotiation_range", [])
                if nr:
                    entry = nr[0]
                    if "min" in entry:
                        flat["budget_min"] = entry["min"]
                    if "max" in entry:
                        flat["budget_max"] = entry["max"]
                for constraint in raw.get("hard_constraints", []):
                    field = constraint.get("field")
                    if field in ("location", "condition", "timing"):
                        flat[field] = constraint["value"]
                sp = raw.get("soft_preferences", [])
                if sp:
                    flat["style_preferences"] = [p["value"] for p in sp]
                db_list = raw.get("dealbreakers")
                if db_list:
                    flat["dealbreakers"] = db_list
                return _MockMessage(
                    content=[_MockToolUseBlock("extract_mandate_fields", flat)],
                    stop_reason="tool_use",
                )

        # Response generation call — return a sensible agent message
        system = kwargs.get("system", "")
        if "mandate" in system.lower():
            reply = "What's your budget for this?"
        else:
            reply = "Nice to meet you! What city are you based in?"
        return _MockMessage(content=[_MockTextBlock(reply)])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = _fake_create
    return mock_client


@pytest.fixture()
def fake_db():
    return FakeSession()


@pytest.fixture()
def client(fake_db):
    mock_llm = _build_mock_anthropic_client()

    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
    with patch("app.services.llm.client.get_llm_client", return_value=mock_llm), \
         patch("app.services.conversation.extractor.get_llm_client", return_value=mock_llm), \
         patch("app.agents.personal_agent.runtime.get_llm_client", return_value=mock_llm), \
         patch("app.agents.mandate_agent.runtime.get_llm_client", return_value=mock_llm):
        with TestClient(app) as test_client:
            yield test_client
    app.dependency_overrides.clear()


@pytest.fixture()
def user_uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def other_user_uuid() -> str:
    return str(uuid.uuid4())


@pytest.fixture()
def now_utc() -> datetime:
    return datetime.now(timezone.utc)
