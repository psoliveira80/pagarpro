---
epic: 10
story: 7
title: "User Registration and Email Verification"
type: "Core"
status: ready-for-dev
---

# Story 10.7: User Registration and Email Verification

## User Story
As a new User,
I want to register an account and verify my email,
So that I can access the system securely.

## Acceptance Criteria

### Backend
1. `POST /api/v1/auth/register` — accepts {full_name, email, password, password_confirmation}. Creates user with `is_active=false`. Sends verification email with token (1h TTL, single-use, hashed in Redis).
2. `POST /api/v1/auth/verify-email` — accepts {token}. Sets `is_active=true`. Returns success.
3. `POST /api/v1/auth/resend-verification` — accepts {email}. Rate limited (3/hour). Always returns 200 (anti-enumeration).
4. Password validation: min 8 chars, at least 1 uppercase, 1 number.
5. Email uniqueness enforced. CPF/CNPJ NOT required at registration (optional, added later in profile).
6. Audit log for register and verify events with category=security.

### Frontend
7. `RegisterComponent` at features/auth/register/ (3 files) — wizard-style form: Step 1 (name + email), Step 2 (password + confirmation), Step 3 (success message "Verifique seu e-mail").
8. `VerifyEmailComponent` at features/auth/verify-email/ — reads token from query param `?token=`, calls API, shows success/error. Auto-redirects to login after 3s.
9. `ResendVerificationComponent` at features/auth/resend-verification/ — email input + "Reenviar" button. Toast on success.
10. Login page: link "Criar conta" below "Esqueci minha senha".
11. Login attempt with unverified email: toast "Verifique seu e-mail antes de entrar".
12. All pages follow glassmorphism pattern (same as login/forgot-password).

### Routes
13. `/auth/register` → RegisterComponent
14. `/auth/verify-email?token=` → VerifyEmailComponent
15. `/auth/resend-verification` → ResendVerificationComponent

## Technical Context

### Files to Create/Modify
```
backend-api/
├── app/api/v1/auth_routes.py                    # Add register, verify-email, resend-verification endpoints
├── app/application/auth/register.py             # RegisterUseCase
├── app/application/auth/verify_email.py         # VerifyEmailUseCase

frontend/
├── src/app/features/auth/register/
│   ├── register.component.ts
│   ├── register.component.html
│   └── register.component.css
├── src/app/features/auth/verify-email/
│   ├── verify-email.component.ts
│   ├── verify-email.component.html
│   └── verify-email.component.css
├── src/app/features/auth/resend-verification/
│   ├── resend-verification.component.ts
│   ├── resend-verification.component.html
│   └── resend-verification.component.css
├── src/app/features/auth/auth.routes.ts         # Add 3 routes
├── src/app/features/auth/login/login.component.html  # Add "Criar conta" link
```

### Dependencies
- Story 1-4 (Auth endpoints, JWT)
- Story 1-10 (Password recovery — same email adapter pattern)

### Technical Notes
- Verification token: `secrets.token_hex(32)`, SHA-256 hash stored in Redis key `email_verify:{hash}` → `{user_id}`, TTL 3600s
- Email sent via `IEmailSender` (ConsoleAdapter in dev, SmtpAdapter in prod) — same pattern as password recovery
- Registration with already-verified email: return 409 "E-mail já cadastrado"
- Login with `is_active=false`: return 403 with message "Verifique seu e-mail"

## Dev Checklist
- [ ] All acceptance criteria met
- [ ] Tests written and passing
- [ ] No regressions
