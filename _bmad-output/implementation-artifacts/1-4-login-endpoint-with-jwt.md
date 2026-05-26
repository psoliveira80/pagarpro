---
epic: 1
story: 4
title: "Login Endpoint with JWT"
type: "Core"
status: done
---

# Story 1.4: Login Endpoint with JWT

## User Story
As an Admin user,
I want to log in with email and password and receive JWT tokens,
So that I can access protected resources.

## Acceptance Criteria

1. **Given** valid credentials, **When** `POST /api/v1/auth/login` is called, **Then** response returns `{access_token, refresh_token, user}` with 200.
2. Passwords verified with Argon2id; failures in <= 200 ms (constant-time); generic `401 Unauthorized`.
3. JWT RS256 with claims `sub`, `email`, `roles`, `iat`, `exp` (15 min), `iss`, `aud`.
4. Refresh token in `HttpOnly Secure SameSite=Lax` cookie, 7 days, rotation on every use.
5. `POST /api/v1/auth/refresh` consumes cookie, invalidates old token, emits new pair.
6. `POST /api/v1/auth/logout` invalidates refresh token (Redis revocation list).
7. **Given** 5 failed attempts in 15 min, **When** 6th arrives, **Then** `429 Too Many Requests` for 15 min.
8. Login events recorded in `audit_log` with HMAC signature.
9. Unit tests: success, wrong password, inactive user, MFA path, rate limit.

## Technical Context

### Architecture References
- **Architecture Section 1.3**: Auth decision — JWT RS256 + refresh cookie.
- **Architecture Section 3.1**: `python-jose` for JWT RS256, `argon2-cffi` for password hashing.
- **Architecture Section 5.2 — Auth endpoints**: `POST /auth/login`, `POST /auth/refresh`, `POST /auth/logout`.
- **Architecture Section 4.2 — Identity**: User entity with `password_hash`, `is_active`, `is_mfa_enabled`.
- **Architecture Section 6**: Security infra in `app/infrastructure/security/`.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── auth_routes.py                # POST /login, /refresh, /logout
│   │       └── schemas/
│   │           └── auth.py                    # LoginRequest, LoginResponse, TokenPair DTOs
│   ├── application/
│   │   └── auth/
│   │       ├── __init__.py
│   │       ├── login.py                       # LoginUseCase
│   │       └── refresh_token.py               # RefreshTokenUseCase
│   ├── domain/
│   │   └── identity/
│   │       ├── __init__.py
│   │       ├── entities.py                    # User domain entity (if not already pure)
│   │       └── policies.py                    # password rules, rate limit rules
│   ├── infrastructure/
│   │   ├── security/
│   │   │   ├── __init__.py
│   │   │   ├── jwt_service.py                 # sign/verify JWT RS256
│   │   │   ├── password_hasher.py             # Argon2id (extend from 1.3)
│   │   │   └── totp.py                        # TOTP placeholder for MFA path
│   │   └── db/
│   │       └── repositories/
│   │           └── user_repo.py               # IUserRepo implementation
│   ├── core/
│   │   └── config.py                          # add JWT_PRIVATE_KEY, JWT_PUBLIC_KEY, JWT_ALGORITHM settings
│   └── tests/
│       └── test_auth.py                       # unit tests for all AC scenarios
```

### Dependencies
- **Story 1.1** (FastAPI skeleton, Redis connection).
- **Story 1.3** (User, Role, RefreshToken tables, audit_log, seed data).

### Technical Notes
- **RS256 keys**: Generate an RSA key pair for JWT signing. Store private key path in `JWT_PRIVATE_KEY_PATH` env var; public key in `JWT_PUBLIC_KEY_PATH`. Load at startup via settings.
- **JWT claims**: `sub` = user UUID, `email`, `roles` = list of role names, `iat`, `exp` = now + 15min, `iss` = `{{product_name}}`, `aud` = `{{product_name}}-api`.
- **Refresh token flow**: Generate a random 64-byte token, SHA-256 hash it, store hash in `refresh_tokens` table. Set the raw token as `HttpOnly Secure SameSite=Lax` cookie named `refresh_token`. On refresh: look up hash, verify not expired/revoked, rotate (create new, revoke old).
- **Rate limiting**: Use Redis to track failed attempts per email. Key: `login_attempts:{email}`, increment on failure, TTL 15 min. On 5th failure, set lockout key with 15 min TTL. Return 429 if locked.
- **Constant-time comparison**: Use `hmac.compare_digest` or Argon2's built-in verify (which is already constant-time).
- **Audit log**: On successful login, record `action='auth.login'`. On failure, record `action='auth.login_failed'`. Both with IP and user-agent from request.
- **MFA path**: If `user.is_mfa_enabled`, return `{mfa_required: true, mfa_token: <temp>}` instead of tokens. The `POST /auth/mfa/verify` endpoint (placeholder for now) verifies TOTP and issues tokens.
- **FastAPI dependency**: Create `get_current_user` dependency in `app/api/deps.py` that decodes JWT from `Authorization: Bearer` header, validates claims, returns user. This will be used by all protected routes.

### Session Context (Pre-Implementation Notes)
- **Folder structure**: code lives under `src/backend-api/`, not bare `backend-api/`
- **Docker-only development**: no local Python runtime; all commands run inside containers
- **External ports**: API=8100, Postgres=5433, Redis=6380 (non-default to avoid collisions)
- **Audit log**: login events MUST use `category='security'` — security category is ALWAYS persisted regardless of config
- **Audit log columns**: include `module` (TEXT), `category` (TEXT), `severity` (TEXT) per session decisions
- **Product name**: `iss` and `aud` JWT claims should use `PRODUCT_NAME` env var, never hardcoded

## Dev Checklist
- [x] All acceptance criteria met
- [x] Tests written and passing
- [x] Lint/type-check passing
- [x] Audit log entries for mutations
- [x] No regressions

## File List
- `src/backend-api/pyproject.toml` — added PyJWT[crypto], pydantic[email]
- `src/backend-api/Dockerfile` — install dev deps
- `src/backend-api/app/infrastructure/settings.py` — JWT & rate limit settings
- `src/backend-api/app/infrastructure/security/jwt_service.py` — JWT RS256 sign/verify
- `src/backend-api/app/infrastructure/security/totp.py` — MFA temp token placeholder
- `src/backend-api/app/infrastructure/db/repositories/__init__.py` — new package
- `src/backend-api/app/infrastructure/db/repositories/user_repo.py` — UserRepository
- `src/backend-api/app/domain/identity/__init__.py` — new package
- `src/backend-api/app/domain/identity/policies.py` — rate limit policies
- `src/backend-api/app/application/auth/__init__.py` — new package
- `src/backend-api/app/application/auth/login.py` — LoginUseCase
- `src/backend-api/app/application/auth/refresh_token.py` — RefreshTokenUseCase, LogoutUseCase
- `src/backend-api/app/api/v1/schemas/__init__.py` — new package
- `src/backend-api/app/api/v1/schemas/auth.py` — auth DTOs
- `src/backend-api/app/api/v1/auth_routes.py` — POST /login, /refresh, /logout
- `src/backend-api/app/api/deps.py` — get_current_user, CurrentUserDep
- `src/backend-api/app/main.py` — registered auth routes
- `src/backend-api/app/tests/conftest.py` — engine lifecycle for tests
- `src/backend-api/app/tests/test_auth.py` — 10 auth tests

## Change Log
- 2026-05-12: Implemented JWT RS256 auth (login/refresh/logout), rate limiting, audit logging, MFA path, 10 tests passing

## Dev Agent Record
### Implementation Plan
- JWT RS256 with ephemeral keys for dev, file-based keys for prod
- Refresh token rotation via SHA-256 hash stored in DB
- Rate limiting via Redis (5 attempts / 15 min lockout)
- Audit logging with category=security for all auth events
- MFA path returns mfa_required flag with temp token

### Completion Notes
All 9 acceptance criteria satisfied. 10 unit/integration tests covering: success, wrong password, nonexistent user, inactive user, MFA path, refresh rotation, logout, rate limiting, no-cookie refresh, JWT claims validation. All 15 tests pass (10 auth + 5 health).
