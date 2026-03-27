import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.routing import APIRouter
from sqlalchemy import text

from app.api.agents import router as agents_router
from app.api.conversations import router as conversations_router
from app.api.mandates import router as mandates_router
from app.api.personal_agent import router as personal_agent_router
from app.api.users import router as users_router
from app.db.session import get_engine

logger = structlog.get_logger(__name__)

app = FastAPI(
    title="Tarp-Space API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)


@app.exception_handler(HTTPException)
async def http_exception_handler(_: Request, exc: HTTPException):
    if isinstance(exc.detail, dict) and "error" in exc.detail:
        payload = exc.detail
    else:
        payload = {
            "error": "server_error",
            "message": str(exc.detail),
            "details": {},
        }
    return JSONResponse(status_code=exc.status_code, content=payload)


api_v1 = APIRouter(prefix="/api/v1")
api_v1.include_router(users_router, prefix="/users", tags=["users"])
api_v1.include_router(agents_router, prefix="/agents", tags=["agents"])
api_v1.include_router(mandates_router, prefix="/mandates", tags=["mandates"])
api_v1.include_router(conversations_router, prefix="/conversations", tags=["conversations"])
api_v1.include_router(personal_agent_router, prefix="/personal-agent", tags=["personal-agent"])

app.include_router(api_v1)


@app.get("/health", tags=["health"])
async def health_check():
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
