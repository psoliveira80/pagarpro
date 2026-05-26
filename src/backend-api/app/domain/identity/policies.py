"""Identity domain policies — rate limiting and password rules."""

from app.infrastructure.settings import get_settings


def max_login_attempts() -> int:
    return get_settings().LOGIN_MAX_ATTEMPTS


def lockout_seconds() -> int:
    return get_settings().LOGIN_LOCKOUT_MINUTES * 60
