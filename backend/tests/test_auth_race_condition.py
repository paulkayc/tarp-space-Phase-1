from datetime import datetime, timezone

from sqlalchemy.exc import IntegrityError

from app.core.auth import get_current_user
from app.db.models import User


class RaceSession:
    def __init__(self):
        self.users = []
        self.pending = None
        self.commit_calls = 0

    class _Query:
        def __init__(self, parent, model):
            self.parent = parent
            self.model = model
            self._filters: dict = {}

        def filter_by(self, **kwargs):
            self._filters = kwargs
            return self

        def all(self):
            items = list(self.parent.users) if self.model is User else []
            for key, value in self._filters.items():
                items = [item for item in items if getattr(item, key, None) == value]
            return items

        def first(self):
            results = self.all()
            return results[0] if results else None

    def query(self, model):
        return self._Query(self, model)

    def add(self, obj):
        self.pending = obj

    def commit(self):
        self.commit_calls += 1
        if self.commit_calls == 1:
            winner = User(
                external_user_id=self.pending.external_user_id,
                email=None,
                display_name=None,
                phone=None,
                persona={},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc),
            )
            self.users.append(winner)
            raise IntegrityError("insert", {}, Exception("duplicate"))
        if self.pending is not None:
            self.users.append(self.pending)
            self.pending = None

    def refresh(self, _obj):
        return None

    def rollback(self):
        self.pending = None


def test_get_current_user_recovers_from_integrity_error_race():
    db = RaceSession()

    user = get_current_user(x_dev_user_id="00000000-0000-0000-0000-000000000001", db=db)

    assert user.external_user_id == "00000000-0000-0000-0000-000000000001"
    assert len(db.users) == 1
