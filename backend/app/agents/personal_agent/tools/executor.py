from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.observability.events import emit_tool_event
from app.agents.personal_agent.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, name: str, **kwargs: Any) -> Any:
        tool = self.registry.get(name)
        if tool is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Tool '{name}' not found"})
        owner_id = str(kwargs.get("owner_id", "unknown"))
        emit_tool_event(owner_id=owner_id, tool_name=name, status="started")
        result = tool.handler(**kwargs)
        emit_tool_event(owner_id=owner_id, tool_name=name, status="completed")
        return result
