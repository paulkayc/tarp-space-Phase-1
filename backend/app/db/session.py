from functools import lru_cache
from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import settings


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency — yields a DB session and closes it after the request."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
