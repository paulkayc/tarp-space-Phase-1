"""
Activity API — ARCHITECTURE.md Section 5
Routes:
  GET /api/v1/agents/{owner_id}/activity
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id

router = APIRouter()


# TODO: implement in Phase 1 observability sprint
