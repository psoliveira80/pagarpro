"""TOTP placeholder for MFA path — will be fully implemented in a future story."""

import secrets


def generate_mfa_temp_token() -> str:
    """Generate a temporary token for the MFA challenge flow."""
    return secrets.token_urlsafe(32)
