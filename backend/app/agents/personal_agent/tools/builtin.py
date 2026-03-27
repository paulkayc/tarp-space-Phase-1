from __future__ import annotations

from uuid import UUID

from app.agents.personal_agent.memory.service import PersonalMemoryService
from app.agents.personal_agent.tools.registry import ToolDefinition, ToolRegistry


def register_builtin_tools(registry: ToolRegistry, memory_service: PersonalMemoryService) -> None:
    registry.register(
        ToolDefinition(
            name="memory_add",
            description="Add a personal memory snippet for the current user.",
            handler=lambda owner_id, content, tags=None, source="inferred", confidence=0.8: memory_service.add_memory(
                owner_id=UUID(str(owner_id)),
                content=content,
                tags=tags,
                source=source,
                confidence=confidence,
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="memory_search",
            description="Search personal memory snippets for the current user.",
            handler=lambda owner_id, query, limit=5: memory_service.search_memories(
                owner_id=UUID(str(owner_id)),
                query=query,
                limit=limit,
            ),
        )
    )
    registry.register(
        ToolDefinition(
            name="memory_update",
            description="Update a personal memory snippet.",
            handler=lambda owner_id, memory_id, content=None, tags=None, is_active=None: memory_service.update_memory(
                owner_id=UUID(str(owner_id)),
                memory_id=UUID(str(memory_id)),
                content=content,
                tags=tags,
                is_active=is_active,
            ),
        )
    )
