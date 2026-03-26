"""
Conversations API — ARCHITECTURE.md Section 5
Routes:
  POST /api/v1/conversations
  POST /api/v1/conversations/{id}/messages   (SSE streaming supported)
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id

router = APIRouter()


# TODO: implement in Phase 1 conversation sprint
