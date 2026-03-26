"""
Auth abstraction — swappable between local dev and cloud JWT.

Local dev  (APP_ENV=development):
    Pass X-Dev-User-Id: <any-string> header.
    No token validation. Trusts the caller completely.
    Never use this mode outside a local network.

Cloud      (APP_ENV=staging | production):
    Pass Authorization: Bearer <jwt>.
    JWT is validated against the configured provider (Clerk or Supabase).
    The provider decision is recorded in TODO below — update when resolved.
"""
from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db


def _require_dev_user_id(x_dev_user_id: str | None = Header(None)) -> str:
    """Extract and require X-Dev-User-Id header in development mode."""
    if not x_dev_user_id:
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "X-Dev-User-Id header is required in development mode",
                "details": {"header": "X-Dev-User-Id"},
            },
        )
    return x_dev_user_id


def _require_jwt(authorization: str | None = Header(None)) -> str:
    """Validate a Bearer JWT and return the provider user ID.

    TODO: implement once auth provider is chosen.
          ARCHITECTURE.md references Supabase; CONTRACTS.md references Clerk.
          Resolve this conflict before implementing cloud auth.

    Implementation steps (when provider is chosen):
      1. Parse 'Bearer <token>' from authorization header
      2. Verify JWT signature using provider's public keys
      3. Extract the 'sub' claim (provider user UUID)
      4. Return the sub claim — it maps to users.clerk_id or users.supabase_user_id
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail={
                "error": "unauthorized",
                "message": "Valid JWT required — Authorization: Bearer <token>",
                "details": {},
            },
        )
    # TODO: replace stub with real JWT validation
    raise HTTPException(
        status_code=501,
        detail={
            "error": "server_error",
            "message": "Cloud JWT auth not yet implemented. Set APP_ENV=development for local use.",
            "details": {},
        },
    )


def get_current_user_id(
    x_dev_user_id: str | None = Header(None),
    authorization: str | None = Header(None),
) -> str:
    """
    FastAPI dependency — returns the authenticated user's external_user_id.

    In development: reads X-Dev-User-Id header directly.
    In cloud:       validates Authorization: Bearer <jwt> and extracts sub claim.

    Usage in routes:
        @router.get("/example")
        def example(owner_id: str = Depends(get_current_user_id)):
            ...
    """
    if settings.app_env == "development":
        return _require_dev_user_id(x_dev_user_id)
    return _require_jwt(authorization)
