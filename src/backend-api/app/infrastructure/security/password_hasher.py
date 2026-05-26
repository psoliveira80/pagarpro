from argon2 import PasswordHasher, Type
from argon2.exceptions import VerifyMismatchError

_ph = PasswordHasher(type=Type.ID)


def hash_password(password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify password against Argon2id hash."""
    try:
        return _ph.verify(stored_hash, password)
    except VerifyMismatchError:
        return False
