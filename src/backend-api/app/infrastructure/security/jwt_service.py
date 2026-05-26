import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
import structlog

from app.infrastructure.settings import get_settings

log = structlog.get_logger()

# Algoritmos JWT permitidos. APENAS RSA assimétrico — proibir HMAC para
# eliminar o vetor de "algorithm confusion" (atacante envia HS256 e força
# o decoder a tratar a chave pública como segredo compartilhado).
_ALLOWED_JWT_ALGORITHMS: tuple[str, ...] = ("RS256", "RS384", "RS512")


_private_key: str | None = None
_public_key: str | None = None


def _load_keys() -> tuple[str, str]:
    global _private_key, _public_key
    if _private_key and _public_key:
        return _private_key, _public_key

    settings = get_settings()

    if settings.JWT_PRIVATE_KEY_PATH and settings.JWT_PUBLIC_KEY_PATH:
        _private_key = Path(settings.JWT_PRIVATE_KEY_PATH).read_text()
        _public_key = Path(settings.JWT_PUBLIC_KEY_PATH).read_text()
    else:
        # Dev-mode: generate ephemeral RSA key pair
        from cryptography.hazmat.primitives.asymmetric import rsa
        from cryptography.hazmat.primitives import serialization

        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        _private_key = key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        _public_key = key.public_key().public_bytes(
            serialization.Encoding.PEM,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode()
        log.warning("jwt_using_ephemeral_keys", hint="Set JWT_PRIVATE_KEY_PATH and JWT_PUBLIC_KEY_PATH for production")

    return _private_key, _public_key


def _resolve_algorithm() -> str:
    """Retorna o algoritmo configurado, recusando qualquer coisa fora da whitelist RSA."""
    settings = get_settings()
    alg = settings.JWT_ALGORITHM
    if alg not in _ALLOWED_JWT_ALGORITHMS:
        raise RuntimeError(
            f"JWT_ALGORITHM='{alg}' não permitido. "
            f"Apenas RSA assimétrico: {_ALLOWED_JWT_ALGORITHMS}. "
            "HMAC (HS*) é proibido por risco de algorithm confusion."
        )
    return alg


def create_access_token(
    *,
    sub: str,
    email: str,
    roles: list[str],
    empresa_id: str,
) -> str:
    settings = get_settings()
    private_key, _ = _load_keys()
    now = datetime.now(timezone.utc)
    payload = {
        "sub": sub,
        "email": email,
        "empresa_id": empresa_id,
        "roles": roles,
        "iat": now,
        "exp": now + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
        "iss": settings.PRODUCT_NAME,
        "aud": f"{settings.PRODUCT_NAME}-api",
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, private_key, algorithm=_resolve_algorithm())


def decode_access_token(token: str) -> dict:
    settings = get_settings()
    _, public_key = _load_keys()
    return jwt.decode(
        token,
        public_key,
        algorithms=list(_ALLOWED_JWT_ALGORITHMS),
        issuer=settings.PRODUCT_NAME,
        audience=f"{settings.PRODUCT_NAME}-api",
    )


def reset_keys() -> None:
    """Reset cached keys — useful for testing."""
    global _private_key, _public_key
    _private_key = None
    _public_key = None
