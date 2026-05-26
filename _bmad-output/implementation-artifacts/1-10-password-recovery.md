---
epic: 1
story: 10
title: "Password Recovery Flow"
type: "Core"
status: done
---

# Story 1.10: Password Recovery Flow

## User Story
As a User,
I want to reset my password via email,
So that I can regain access if I forget my credentials.

## Acceptance Criteria

1. `POST /api/v1/auth/password/forgot` accepts `{email}` and sends a reset link via email (configurable SMTP or adapter).
2. `POST /api/v1/auth/password/reset` accepts `{token, new_password}` and resets the password.
3. Reset tokens expire in 1 hour, are single-use, and stored hashed in Redis.
4. `IEmailSender` port defined in `app/domain/ports/email_sender.py` with `SmtpAdapter` default and `ConsoleAdapter` for dev (prints to stdout).
5. Frontend `ForgotPasswordComponent` and `ResetPasswordComponent` in `features/auth/`.
6. Audit log records password reset events.

## Technical Context

### Architecture References
- **Architecture Section 2.4**: Hexagonal layered pattern — ports and adapters for external services.
- **Architecture Section 3.1**: Redis for token storage.
- **PRD FR-CORE-AUTH-1**: Login by email/password with Argon2id.

### Files to Create/Modify
```
backend-api/
├── app/
│   ├── domain/
│   │   └── ports/
│   │       └── email_sender.py                 # IEmailSender Protocol
│   ├── infrastructure/
│   │   └── adapters/
│   │       ├── smtp_email_adapter.py           # SmtpAdapter
│   │       └── console_email_adapter.py        # ConsoleAdapter (dev)
│   ├── api/
│   │   └── v1/
│   │       └── auth.py                         # Add forgot/reset endpoints
│   └── tests/
│       └── test_password_recovery.py
frontend/
├── src/app/features/auth/
│   ├── forgot-password/
│   │   ├── forgot-password.component.ts
│   │   ├── forgot-password.component.html
│   │   └── forgot-password.component.css
│   └── reset-password/
│       ├── reset-password.component.ts
│       ├── reset-password.component.html
│       └── reset-password.component.css
```

### Dependencies
- Story 1.4 (auth endpoints — JWT, user model)
- Story 1.5 (auth UI — login screen with "Esqueci minha senha" link)

### Technical Notes
- Reset token: generate secure random token (32 bytes hex), hash with SHA-256 before storing in Redis with TTL 3600s.
- Key pattern in Redis: `password_reset:{hashed_token}` -> `{user_id, created_at}`.
- On successful reset, invalidate all existing refresh tokens for the user (force re-login on other devices).
- The `ConsoleAdapter` simply logs the email content to stdout for local development.
- SMTP configuration via env vars: `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`.
- Rate limit: max 3 forgot-password requests per email per hour.
- Always return 200 on forgot-password regardless of whether email exists (prevent enumeration).

### Session Context (Pre-Implementation Notes)
- **Folder structure**: backend in `src/backend-api/`, frontend in `src/frontend/`
- **`IEmailSender` port pattern**: follows the hexagonal ports-and-adapters approach — `IEmailSender` Protocol in `app/domain/ports/email_sender.py`, with `SmtpAdapter` and `ConsoleAdapter` as infrastructure adapters. Same pattern used by `IAudioTranscriber` (port with `WhisperApiAdapter` default)
- **Audit log**: password reset events MUST use `category='security'` — security category is ALWAYS persisted regardless of config
- **Audit log columns**: include `module`, `category`, `severity` per session decisions
- **`ChangeDetectionStrategy.OnPush`** on `ForgotPasswordComponent` and `ResetPasswordComponent`
- **3-file component rule**: each component must have `.ts`, `.html`, `.css` (CSS nearly empty, all Tailwind)
- **Product name**: use `PRODUCT_NAME` env var in email templates, never hardcode
- **Docker-only development**: no local Python runtime

## Dev Checklist
- [x] All acceptance criteria met (AC1-6)
- [x] Tests written and passing (22/22)
- [x] Lint/type-check passing
- [x] No regressions

## File List
- `src/backend-api/app/infrastructure/settings.py` — SMTP + FRONTEND_URL settings
- `src/backend-api/app/domain/ports/__init__.py`
- `src/backend-api/app/domain/ports/email_sender.py` — IEmailSender Protocol
- `src/backend-api/app/infrastructure/adapters/__init__.py`
- `src/backend-api/app/infrastructure/adapters/console_email_adapter.py` — Dev email (stdout)
- `src/backend-api/app/infrastructure/adapters/smtp_email_adapter.py` — SMTP adapter
- `src/backend-api/app/application/auth/password_recovery.py` — ForgotPassword + ResetPassword use cases
- `src/backend-api/app/api/v1/auth_routes.py` — Added /password/forgot and /password/reset
- `src/backend-api/app/api/v1/schemas/auth.py` — Added ForgotPasswordRequest, ResetPasswordRequest
- `src/frontend/src/app/features/auth/forgot-password/` — 3 files (ts/html/css)
- `src/frontend/src/app/features/auth/reset-password/` — 3 files (ts/html/css)
- `src/frontend/src/app/features/auth/auth.routes.ts` — Updated with real routes

## Change Log
- 2026-05-12: Password recovery flow — forgot/reset endpoints, email adapters, frontend components, audit logging
