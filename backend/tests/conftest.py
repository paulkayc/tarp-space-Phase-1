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

    def flush(self):
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


def _inline_extract_persona(text: str) -> dict:
    """Minimal inline persona extractor used by the test mock (no regex fallback)."""
    import re
    delta: dict = {}
    low = text.lower()

    # name
    for pat in [r"my name is ([a-z]+)", r"i'?m ([a-z]+)", r"i am ([a-z]+)", r"call me ([a-z]+)"]:
        m = re.search(pat, low)
        if m and m.group(1) not in {"a", "an", "the", "not", "just", "here", "looking", "sure"}:
            delta["name"] = m.group(1).capitalize()
            break

    # home_city
    for pat in [r"i live in ([a-z][a-z\s]{1,30})", r"i'?m based in ([a-z][a-z\s]{1,30})",
                r"i'?m from ([a-z][a-z\s]{1,30})", r"based in ([a-z][a-z\s]{1,30})"]:
        m = re.search(pat, low)
        if m:
            city = re.split(r"\b(and|but|so|where|when|with|the|it)\b", m.group(1))[0].strip(" .,!?")
            if city:
                delta["home_city"] = city.title()
            break

    # communication_style
    if any(t in low for t in ["brief", "concise", "short", "quick summary", "quick summaries"]):
        delta["communication_style"] = "brief"
    elif any(t in low for t in ["detailed", "comprehensive", "full detail"]):
        delta["communication_style"] = "detailed"

    # general_interests
    _interest_tokens = {
        "furniture": {"sofa", "couch", "table", "desk", "chair", "dresser", "bed", "furniture"},
        "electronics": {"laptop", "phone", "tv", "television", "monitor", "electronics"},
        "cars": {"car", "sedan", "suv", "truck", "vehicle"},
        "appliances": {"fridge", "refrigerator", "washer", "dryer", "stove", "microwave", "appliance"},
    }
    found_interests = [cat for cat, tokens in _interest_tokens.items() if any(t in low for t in tokens)]
    if found_interests:
        delta["general_interests"] = found_interests

    # deal_sensitivity
    if any(t in low for t in ["best price", "cheapest", "bargain", "affordable", "price matters"]):
        delta["deal_sensitivity"] = "price_first"
    elif any(t in low for t in ["best quality", "premium", "high quality", "quality matters"]):
        delta["deal_sensitivity"] = "quality_first"
    elif any(t in low for t in ["fastest", "convenience", "near me"]):
        delta["deal_sensitivity"] = "convenience_first"

    return delta


def _inline_extract_mandate(text: str) -> dict:
    """Minimal inline mandate extractor used by the test mock (no regex fallback)."""
    import re
    low = text.lower()
    flat: dict = {}

    # intent
    if "sell" in low:
        flat["intent_type"] = "sell"
        flat["vertical"] = "goods"
    elif any(t in low for t in ["buy", "looking for", "need", "want", "i need"]):
        flat["intent_type"] = "buy"
        flat["vertical"] = "goods"

    # category — keyword table
    _cats = {
        "furniture": {"sofa", "couch", "table", "desk", "chair", "dresser", "bed", "furniture"},
        "car": {"car", "sedan", "suv", "truck"},
        "appliance": {"fridge", "refrigerator", "washer", "dryer", "stove", "microwave", "appliance"},
        "electronics": {"laptop", "phone", "tv", "television", "monitor"},
    }
    for cat, tokens in _cats.items():
        if any(t in low for t in tokens):
            flat["category"] = cat
            break

    # budget
    rng = re.search(r"\$?\s*(\d{2,6})\s*(?:-|to)\s*\$?\s*(\d{2,6})", low)
    if rng:
        flat["budget_min"] = float(min(rng.group(1), rng.group(2)))
        flat["budget_max"] = float(max(rng.group(1), rng.group(2)))
    else:
        mx = re.search(r"(?:under|below|less than|max)\s*\$?\s*(\d{2,6})", low)
        if mx:
            flat["budget_max"] = float(mx.group(1))
        mn = re.search(r"(?:at least|minimum|min)\s*\$?\s*(\d{2,6})", low)
        if mn:
            flat["budget_min"] = float(mn.group(1))

    # condition
    for cond in ["like new", "excellent", "good", "fair", "used", "new"]:
        if cond in low:
            flat["condition"] = cond
            break

    # timing
    if "asap" in low:
        flat["timing"] = "asap"
    else:
        wm = re.search(r"within\s+([a-z0-9\s-]{1,20})", low)
        if wm:
            flat["timing"] = wm.group(1).strip(" .,")

    return flat


def _build_mock_anthropic_client() -> MagicMock:
    """Return a mock Anthropic client whose messages.create() simulates extraction."""

    def _fake_create(**kwargs):
        tools = kwargs.get("tools", [])
        messages = kwargs.get("messages", [])

        # Find the last user message
        user_content = ""
        for msg in reversed(messages):
            if msg.get("role") == "user":
                c = msg.get("content", "")
                if isinstance(c, str):
                    user_content = c
                break

        if tools:
            tool_name = tools[0]["name"]

            if tool_name == "extract_persona_fields":
                delta = _inline_extract_persona(user_content)
                return _MockMessage(
                    content=[_MockToolUseBlock("extract_persona_fields", delta)],
                    stop_reason="tool_use",
                )

            if tool_name == "extract_mandate_fields":
                flat = _inline_extract_mandate(user_content)
                return _MockMessage(
                    content=[_MockToolUseBlock("extract_mandate_fields", flat)],
                    stop_reason="tool_use",
                )

        # Response generation call
        system = kwargs.get("system", "")
        reply = (
            "What's your budget for this?"
            if "mandate" in system.lower()
            else "Nice to meet you! What city are you based in?"
        )
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
