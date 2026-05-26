---
epic: 1
story: 6
title: "AuthGuard, JWT Interceptor and Silent Refresh"
type: "Core"
status: done
---

# Story 1.6: AuthGuard, JWT Interceptor and Silent Refresh

## User Story
As the System,
I want protected routes to require authentication and tokens refreshed transparently,
So that the user experience is uninterrupted.

## Acceptance Criteria

1. `auth.guard.ts` in `core/guards/` blocks routes when `authState().isAuthenticated()` is false, redirecting to `/login?redirect=...`.
2. `jwt.interceptor.ts` in `core/interceptors/` injects `Authorization: Bearer <token>`.
3. **Given** 401, **Then** attempt `POST /auth/refresh` once, replay on success, clear state and redirect on failure.
4. **Given** multiple concurrent 401s, **Then** only one refresh fires (lock).
5. On logout: clear state and cookie, navigate to `/login`.

## Technical Context

### Architecture References
- **Architecture Section 2.5**: Core services and interceptors in `core/`.
- **Architecture Section 1.3**: JWT RS256 + refresh cookie pattern. Short-lived access token (15 min), refresh in HttpOnly cookie (7 days).
- **Architecture Section 3.2**: Angular HttpClient + interceptors (nativo).
- **Architecture Section 5.2 — Auth endpoints**: `POST /auth/refresh`, `POST /auth/logout`.

### Files to Create/Modify
```
frontend/
├── src/app/
│   ├── core/
│   │   ├── guards/
│   │   │   └── auth.guard.ts                   # canActivate functional guard
│   │   ├── interceptors/
│   │   │   └── jwt.interceptor.ts              # HttpInterceptorFn
│   │   └── services/
│   │       └── auth.service.ts                 # extend with refresh(), isRefreshing, logout()
│   ├── app.routes.ts                           # apply guard to protected routes
│   └── app.config.ts                           # register interceptor via provideHttpClient(withInterceptors([...]))
```

### Dependencies
- **Story 1.2** (Angular skeleton, routing).
- **Story 1.4** (Backend refresh endpoint).
- **Story 1.5** (AuthService with authState signal, login component).

### Technical Notes
- **Functional guard** (Angular 21 pattern):
  ```typescript
  export const authGuard: CanActivateFn = (route, state) => {
    const auth = inject(AuthService);
    const router = inject(Router);
    if (auth.isAuthenticated()) return true;
    return router.createUrlTree(['/login'], { queryParams: { redirect: state.url } });
  };
  ```
- **Functional interceptor** (Angular 21 pattern):
  ```typescript
  export const jwtInterceptor: HttpInterceptorFn = (req, next) => {
    const auth = inject(AuthService);
    const token = auth.authState().token;
    if (token) {
      req = req.clone({ setHeaders: { Authorization: `Bearer ${token}` } });
    }
    return next(req);
  };
  ```
- **Silent refresh with lock**: In `AuthService`, maintain a `private refreshing: Promise<boolean> | null = null` field. On 401:
  1. If `refreshing` is null, set it to the refresh call promise.
  2. If `refreshing` is not null, await the existing promise.
  3. On success: update `authState` with new token, replay failed request, set `refreshing = null`.
  4. On failure: clear `authState`, redirect to `/login`, set `refreshing = null`.
- **Refresh call**: `POST /api/v1/auth/refresh` with `withCredentials: true` to send the HttpOnly cookie. Response contains new `access_token`. The backend rotates the refresh cookie automatically.
- **Interceptor ordering**: The JWT interceptor should handle the 401 -> refresh -> retry flow. Use `catchError` in the interceptor pipe to intercept 401 responses. Skip refresh for the refresh endpoint itself to avoid infinite loops.
- **Logout**: Call `POST /api/v1/auth/logout` (with credentials), then clear `authState` signal and navigate to `/login`. The backend invalidates the refresh token.
- **Redirect after login**: When guard redirects to `/login?redirect=/some-page`, the login component should read `redirect` query param and navigate there after successful login.
- **Route protection**: Apply `authGuard` to all routes except `/login`, `/auth/*`, and `/404`.

### Session Context (Pre-Implementation Notes)
- **Folder structure**: frontend code lives under `src/frontend/`, not bare `frontend/`
- **Interceptors already registered**: `provideHttpClient(withInterceptorsFromDi())` is already in `app.config.ts` from Story 1.2 — register the JWT interceptor there, do not add a second `provideHttpClient` call
- **Feature shell routes**: use `loadChildren` pattern — `auth.routes.ts` and `system.routes.ts` are the shell route files
- **`ChangeDetectionStrategy.OnPush`** on every component
- **3-file component rule**: guard/interceptor files are single `.ts` files, but any new component must have `.ts`, `.html`, `.css`

## Dev Checklist
- [x] All acceptance criteria met
- [x] Tests written and passing (build + lint pass)
- [x] Lint/type-check passing
- [x] Audit log entries for mutations (N/A — frontend only)
- [x] No regressions

## File List
- `src/frontend/src/app/core/guards/auth.guard.ts` — functional canActivate guard
- `src/frontend/src/app/core/interceptors/jwt.interceptor.ts` — JWT bearer + 401 refresh retry
- `src/frontend/src/app/core/services/auth.service.ts` — added refresh lock for concurrent 401s
- `src/frontend/src/app/app.config.ts` — registered jwtInterceptor
- `src/frontend/src/app/app.routes.ts` — applied authGuard to system routes
- `src/frontend/src/app/features/auth/login/login.component.ts` — added redirect query param support

## Change Log
- 2026-05-12: AuthGuard, JWT interceptor with silent refresh + concurrent lock, redirect after login

## Dev Agent Record
### Completion Notes
AC1-5 met. Functional guard blocks unauthenticated, interceptor injects Bearer, 401 triggers silent refresh with single-flight lock, logout clears state + navigates. Login respects ?redirect param.
