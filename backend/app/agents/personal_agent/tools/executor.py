from __future__ import annotations

from typing import Any

from fastapi import HTTPException

from app.agents.personal_agent.tools.registry import ToolRegistry


class ToolExecutor:
    def __init__(self, registry: ToolRegistry):
        self.registry = registry

    def execute(self, name: str, **kwargs: Any) -> Any:
        tool = self.registry.get(name)
        if tool is None:
            raise HTTPException(status_code=404, detail={"error": "not_found", "message": f"Tool '{name}' not found"})
        return tool.handler(**kwargs)
