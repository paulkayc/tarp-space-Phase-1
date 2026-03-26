"""
Inventory API — ARCHITECTURE.md Section 5
Routes:
  GET  /api/v1/inventory    (admin)
  POST /api/v1/inventory    (admin)
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id

router = APIRouter()


# TODO: implement in Phase 1 seed/admin sprint
