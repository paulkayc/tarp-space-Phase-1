from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


@lru_cache(maxsize=1)
def get_engine():
    return create_engine(
        settings.database_url,
        pool_pre_ping=True,
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=get_engine())
