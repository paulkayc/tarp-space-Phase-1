import structlog
from fastapi import FastAPI
from sqlalchemy import text

from app.core.config import settings
from app.db.session import get_engine

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Tarp-Space API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.get("/health")
async def health_check():
    """Health check — verifies app is running and database is reachable."""
    db_status = "ok"
    try:
        engine = get_engine()
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:
        logger.error("health_check_db_error", error=str(exc))
        db_status = "error"

    return {
        "status": "ok",
        "db": db_status,
        "version": "1.0.0",
    }
