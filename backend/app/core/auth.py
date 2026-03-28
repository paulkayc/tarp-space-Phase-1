from datetime import datetime, timezone
from uuid import UUID

from fastapi import Depends, Header, HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import User
from app.db.session import get_db


def _unauthorized(message: str) -> None:
    raise HTTPException(
        status_code=401,
        detail={
            "error": "unauthorized",
            "message": message,
        },
    )


def _get_user_by_dev_user_id(db: Session, dev_user_id: str) -> User | None:
    return db.query(User).filter_by(external_user_id=dev_user_id).first()


def get_current_user(
    x_dev_user_id: str | None = Header(default=None, alias="X-Dev-User-Id"),
    db: Session = Depends(get_db),
) -> User:
    if x_dev_user_id is None:
        _unauthorized("X-Dev-User-Id header required")

    try:
        parsed_dev_user_id = str(UUID(x_dev_user_id))
    except (TypeError, ValueError):
        _unauthorized("X-Dev-User-Id must be a valid UUID")

    user = _get_user_by_dev_user_id(db, parsed_dev_user_id)
    if user is not None:
        return user

    now = datetime.now(timezone.utc)
    user = User(
        external_user_id=parsed_dev_user_id,
        email=None,
        display_name=None,
        phone=None,
        persona={},
        created_at=now,
        updated_at=now,
    )
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
        return user
    except IntegrityError:
        # Concurrent request created the same external_user_id in between our
        # read and insert. Recover by rolling back and returning the winner row.
        db.rollback()
        existing = _get_user_by_dev_user_id(db, parsed_dev_user_id)
        if existing is not None:
            return existing
        raise


def get_current_user_id(current_user: User = Depends(get_current_user)) -> str:
    return str(current_user.id)
