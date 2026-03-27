import uuid
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from app.db.session import get_db
from app.main import app


class FakeQuery:
    def __init__(self, session, model):
        self._session = session
        self._model = model

    def all(self):
        return list(self._session._data.get(self._model, []))


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


@pytest.fixture()
def fake_db():
    return FakeSession()


@pytest.fixture()
def client(fake_db):
    def override_get_db():
        yield fake_db

    app.dependency_overrides[get_db] = override_get_db
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
