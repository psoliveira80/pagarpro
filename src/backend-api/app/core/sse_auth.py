"""JWT authentication for SSE endpoints (via query param)."""

from uuid import UUID

from jwt import InvalidTokenError

from app.infrastructure.security.jwt_service import decode_access_token


def validate_sse_token(token: str) -> UUID | None:
    """Validate JWT from SSE query param, return user_id or None."""
    try:
        payload = decode_access_token(token)
        return UUID(payload["sub"])
    except (InvalidTokenError, KeyError, ValueError):
        return None
