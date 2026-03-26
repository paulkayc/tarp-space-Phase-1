"""
Mandates API — ARCHITECTURE.md Section 5
Routes:
  GET    /api/v1/mandates/{mandate_id}
  PATCH  /api/v1/mandates/{mandate_id}
  POST   /api/v1/mandates/{mandate_id}/confirm
  GET    /api/v1/mandates/{mandate_id}/history
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id

router = APIRouter()


# TODO: implement in Phase 1 mandate sprint
