from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.models import PersonalMemory, PersonalMemoryEvent


class PersonalMemoryService:
    def __init__(self, db: Session):
        self.db = db

    def _all_memories(self) -> list[PersonalMemory]:
        return list(self.db.query(PersonalMemory).all())

    def _all_events(self) -> list[PersonalMemoryEvent]:
        return list(self.db.query(PersonalMemoryEvent).all())

    def add_memory(
        self,
        owner_id: UUID,
        content: str,
        tags: list[str] | None = None,
        source: str = "inferred",
        confidence: float = 0.8,
    ) -> PersonalMemory:
        now = datetime.now(timezone.utc)
        memory = PersonalMemory(
            id=uuid4(),
            owner_id=owner_id,
            content=content,
            tags=tags or [],
            source=source,
            confidence=confidence,
            is_active=True,
            created_at=now,
            updated_at=now,
        )
        self.db.add(memory)
        self.db.add(
            PersonalMemoryEvent(
                id=uuid4(),
                memory_id=memory.id,
                owner_id=owner_id,
                event_type="created",
                previous_content=None,
                new_content=content,
                created_at=now,
            )
        )
        self.db.commit()
        self.db.refresh(memory)
        return memory

    def list_memories(self, owner_id: UUID, include_inactive: bool = False) -> list[PersonalMemory]:
        items = [m for m in self._all_memories() if m.owner_id == owner_id]
        if not include_inactive:
            items = [m for m in items if m.is_active]
        items.sort(key=lambda item: item.updated_at, reverse=True)
        return items

    def search_memories(self, owner_id: UUID, query: str, limit: int = 5) -> list[PersonalMemory]:
        normalized_query = query.lower().strip()
        matches: list[tuple[int, PersonalMemory]] = []

        for memory in self.list_memories(owner_id=owner_id):
            haystack = f"{memory.content} {' '.join(memory.tags or [])}".lower()
            score = 0
            if normalized_query in haystack:
                score += 5
            for token in normalized_query.split():
                if token and token in haystack:
                    score += 1
            if score > 0:
                matches.append((score, memory))

        matches.sort(key=lambda item: (item[0], item[1].updated_at), reverse=True)
        return [memory for _, memory in matches[: max(1, limit)]]

    def get_memory(self, owner_id: UUID, memory_id: UUID) -> PersonalMemory | None:
        for memory in self._all_memories():
            if memory.id == memory_id and memory.owner_id == owner_id:
                return memory
        return None

    def update_memory(
        self,
        owner_id: UUID,
        memory_id: UUID,
        content: str | None = None,
        tags: list[str] | None = None,
        is_active: bool | None = None,
    ) -> PersonalMemory | None:
        memory = self.get_memory(owner_id=owner_id, memory_id=memory_id)
        if memory is None:
            return None

        now = datetime.now(timezone.utc)
        previous_content = memory.content
        was_active = bool(memory.is_active)

        if content is not None:
            memory.content = content
        if tags is not None:
            memory.tags = tags
        if is_active is not None:
            memory.is_active = is_active
        memory.updated_at = now

        event_type = "updated"
        if is_active is False:
            event_type = "deactivated"
        elif is_active is True and not was_active:
            event_type = "reactivated"

        self.db.add(
            PersonalMemoryEvent(
                id=uuid4(),
                memory_id=memory.id,
                owner_id=owner_id,
                event_type=event_type,
                previous_content=previous_content,
                new_content=memory.content,
                created_at=now,
            )
        )
        self.db.commit()
        self.db.refresh(memory)
        return memory
