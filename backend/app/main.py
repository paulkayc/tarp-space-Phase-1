import structlog
from fastapi import FastAPI
from fastapi.routing import APIRouter
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

# ---------------------------------------------------------------------------
# /api/v1 router — all application endpoints mount here.
# ---------------------------------------------------------------------------
api_v1 = APIRouter(prefix="/api/v1")

from app.api.users import router as users_router, agents_router
from app.api.onboarding import router as onboarding_router

api_v1.include_router(users_router)
api_v1.include_router(agents_router)
api_v1.include_router(onboarding_router)

# TODO: include remaining routers as they are built:
# from app.api.conversations import router as conversations_router
# from app.api.mandates import router as mandates_router
# from app.api.search import router as search_router
# from app.api.inventory import router as inventory_router
# from app.api.activity import router as activity_router

app.include_router(api_v1)


# ---------------------------------------------------------------------------
# Health check — public, no auth required (CONTRACTS.md C1.1)
# ---------------------------------------------------------------------------
@app.get("/health", tags=["health"])
async def health_check():
    """
    Health check — verifies app is running and database is reachable.

    Response shape per CONTRACTS.md C1.1:
      { "status": "ok", "db": "ok", "redis": "n/a", "version": "1.0.0" }

    redis is "n/a" in local dev (not in Phase 1 stack per ARCHITECTURE.md).
    """
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
        "redis": "n/a",
        "version": "1.0.0",
    }
