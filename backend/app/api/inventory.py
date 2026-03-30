"""
Inventory API — ARCHITECTURE.md Section 5
Routes:
  GET  /api/v1/inventory    list active inventory (admin)
  POST /api/v1/inventory    add a new listing (admin)
"""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Inventory
from app.db.session import get_db

router = APIRouter()


def _require_admin(x_agent_admin_key: str | None = Header(default=None, alias="X-Agent-Admin-Key")) -> None:
    if not x_agent_admin_key or x_agent_admin_key != settings.admin_api_key:
        raise HTTPException(
            status_code=403,
            detail={"error": "forbidden", "message": "Admin key required"},
        )


class InventoryCreateRequest(BaseModel):
    vertical: str = Field(..., description="goods or services")
    category: str
    title: str
    description: str
    price: float
    price_negotiable: bool = True
    location_raw: str | None = None
    metadata: dict = Field(default_factory=dict)


def _serialize_inventory(item: Inventory) -> dict:
    return {
        "id": str(item.id),
        "vertical": item.vertical,
        "category": item.category,
        "title": item.title,
        "description": item.description,
        "price": float(item.price),
        "price_negotiable": item.price_negotiable,
        "location_raw": item.location_raw,
        "metadata": item.metadata_json or {},
        "has_embedding": item.embedding is not None,
        "is_active": item.is_active,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


@router.get("")
def list_inventory(
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
):
    items = db.query(Inventory).filter_by(is_active=True).all()
    return {
        "inventory": [_serialize_inventory(i) for i in items],
        "total": len(items),
    }


@router.post("", status_code=201)
def create_inventory_item(
    body: InventoryCreateRequest,
    db: Session = Depends(get_db),
    _admin: None = Depends(_require_admin),
):
    if body.vertical not in ("goods", "services"):
        raise HTTPException(
            status_code=422,
            detail={"error": "validation_error", "message": "vertical must be 'goods' or 'services'"},
        )

    now = datetime.now(timezone.utc)
    item = Inventory(
        id=uuid4(),
        vertical=body.vertical,
        category=body.category,
        title=body.title,
        description=body.description,
        metadata_json=body.metadata,
        price=body.price,
        price_negotiable=body.price_negotiable,
        location_raw=body.location_raw,
        embedding=None,  # populated async by embedding pipeline
        is_active=True,
        created_at=now,
        updated_at=now,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _serialize_inventory(item)
