"""
Search API — ARCHITECTURE.md Section 5
Routes:
  POST /api/v1/mandates/{mandate_id}/search
  POST /api/v1/mandates/{mandate_id}/signals
"""
from fastapi import APIRouter, Depends

from app.core.auth import get_current_user_id

router = APIRouter()


# TODO: implement in Phase 1 matching sprint
