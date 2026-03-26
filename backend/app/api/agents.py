from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.db.models import Mandate, User
from app.db.session import get_db

router = APIRouter()


@router.get("/me")
def get_agent_me(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    user_mandates = [m for m in db.query(Mandate).all() if m.owner_id == current_user.id]
    active_mandate_count = sum(1 for m in user_mandates if m.is_active or m.confirmed_at is not None)
    status = "active" if active_mandate_count > 0 else "inactive"

    return {
        "id": str(current_user.id),
        "owner_id": str(current_user.id),
        "status": status,
        "reputation_score": 0.5,
        "active_mandate_count": active_mandate_count,
        "completed_negotiation_count": 0,
        "created_at": current_user.created_at,
    }
