from __future__ import annotations

from fastapi import Header, HTTPException

from app.core.config import settings


def require_agent_admin(
    x_agent_admin_key: str | None = Header(default=None, alias="X-Agent-Admin-Key"),
) -> dict[str, bool]:
    if not x_agent_admin_key or x_agent_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Agent admin privileges required"},
        )
    return {"agent_admin": True}
