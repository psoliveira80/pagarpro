import structlog
from fastapi import APIRouter, HTTPException, Request, Response
from redis.asyncio import Redis

from app.api.deps import CurrentUserDep, SessionDep
from app.api.v1.schemas.auth import (
    ForgotPasswordRequest,
    LoginRequest,
    LoginResponse,
    MessageResponse,
    MfaRequiredResponse,
    RegisterRequest,
    ResendVerificationRequest,
    ResetPasswordRequest,
    TokenRefreshResponse,
    UserResponse,
    VerifyEmailRequest,
)
from app.application.auth.login import InvalidCredentialsError, LoginUseCase, RateLimitError, UserInactiveError
from app.application.auth.password_recovery import (
    ForgotPasswordUseCase,
    InvalidResetTokenError,
    ResetPasswordUseCase,
)
from app.application.auth.refresh_token import (
    InvalidRefreshTokenError,
    LogoutUseCase,
    RefreshTokenUseCase,
)
from app.application.auth.register import (
    ResendVerificationUseCase,
)
from app.application.auth.verify_email import (
    InvalidVerifyTokenError,
    VerifyEmailUseCase,
)
from app.infrastructure.settings import get_settings

log = structlog.get_logger()

router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"


def _is_secure() -> bool:
    return get_settings().APP_ENV != "dev"


def _set_refresh_cookie(response: Response, token_hex: str, max_age: int) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token_hex,
        httponly=True,
        secure=_is_secure(),
        samesite="lax",
        max_age=max_age,
        path="/api/v1/auth",
    )


def _clear_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        key=REFRESH_COOKIE,
        httponly=True,
        secure=_is_secure(),
        samesite="lax",
        path="/api/v1/auth",
    )


def _parse_refresh_cookie(request: Request) -> str:
    """Extract and validate the refresh token cookie hex value."""
    raw_token_hex = request.cookies.get(REFRESH_COOKIE)
    if not raw_token_hex:
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        bytes.fromhex(raw_token_hex)
    except ValueError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return raw_token_hex


@router.post("/login", response_model=LoginResponse | MfaRequiredResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: SessionDep,
) -> LoginResponse | MfaRequiredResponse:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)
    try:
        uc = LoginUseCase(session, redis)
        result = await uc.execute(
            email=body.email,
            password=body.password,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except UserInactiveError:
        raise HTTPException(status_code=403, detail="Verifique seu e-mail antes de entrar")
    except InvalidCredentialsError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    except RateLimitError:
        raise HTTPException(status_code=429, detail="Too many login attempts. Try again later.")
    finally:
        await redis.aclose()

    if result.mfa_required:
        return MfaRequiredResponse(mfa_token=result.mfa_token)  # type: ignore[arg-type]

    # Set refresh token cookie
    max_age = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    _set_refresh_cookie(response, result.refresh_token_raw, max_age)  # type: ignore[arg-type]

    user = result.user
    assert user is not None
    return LoginResponse(
        access_token=result.access_token,  # type: ignore[arg-type]
        user=UserResponse(
            id=str(user.id),
            email=user.email,
            full_name=user.nome_completo,
            roles=[r.nome for r in user.perfis],
            is_mfa_enabled=user.mfa_ativo,
        ),
    )


@router.post("/refresh", response_model=TokenRefreshResponse)
async def refresh(
    request: Request,
    response: Response,
    session: SessionDep,
) -> TokenRefreshResponse:
    raw_token_hex = _parse_refresh_cookie(request)

    try:
        uc = RefreshTokenUseCase(session)
        result = await uc.execute(raw_token_hex=raw_token_hex)
    except InvalidRefreshTokenError:
        _clear_refresh_cookie(response)
        raise HTTPException(status_code=401, detail="Unauthorized")

    settings = get_settings()
    max_age = settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS * 86400
    _set_refresh_cookie(response, result.refresh_token_raw, max_age)

    return TokenRefreshResponse(access_token=result.access_token)


@router.get("/me", response_model=UserResponse)
async def get_me(current_user: CurrentUserDep) -> UserResponse:
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        full_name=current_user.nome_completo,
        roles=[r.nome for r in current_user.perfis],
        is_mfa_enabled=current_user.mfa_ativo,
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    session: SessionDep,
) -> MessageResponse:
    raw_token_hex = request.cookies.get(REFRESH_COOKIE)
    if raw_token_hex:
        try:
            bytes.fromhex(raw_token_hex)
        except ValueError:
            pass
        else:
            uc = LogoutUseCase(session)
            await uc.execute(raw_token_hex=raw_token_hex)

    _clear_refresh_cookie(response)
    return MessageResponse(detail="Logged out successfully")


@router.post("/password/forgot", response_model=MessageResponse)
async def forgot_password(
    body: ForgotPasswordRequest,
    session: SessionDep,
) -> MessageResponse:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    # Use ConsoleAdapter in dev, SmtpAdapter in prod
    if settings.SMTP_HOST:
        from app.infrastructure.adapters.smtp_email_adapter import SmtpEmailAdapter

        email_sender = SmtpEmailAdapter()
    else:
        from app.infrastructure.adapters.console_email_adapter import ConsoleEmailAdapter

        email_sender = ConsoleEmailAdapter()

    try:
        uc = ForgotPasswordUseCase(session, redis, email_sender)
        await uc.execute(email=body.email)
    finally:
        await redis.aclose()

    # Always 200 — prevent email enumeration
    return MessageResponse(detail="If the email exists, a reset link was sent.")


@router.post("/password/reset", response_model=MessageResponse)
async def reset_password(
    body: ResetPasswordRequest,
    request: Request,
    session: SessionDep,
) -> MessageResponse:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        uc = ResetPasswordUseCase(session, redis)
        await uc.execute(
            token=body.token,
            new_password=body.new_password,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidResetTokenError:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")
    finally:
        await redis.aclose()

    return MessageResponse(detail="Password reset successfully")


@router.post("/register", response_model=MessageResponse, status_code=410)
async def register(
    _body: RegisterRequest,
) -> MessageResponse:
    """Auto-cadastro desabilitado: cada usuário pertence a uma empresa específica
    (Modelo A multi-tenant). Novos usuários são criados via convite enviado pelo
    administrador da empresa. Este endpoint responde 410 Gone até que o fluxo de
    convite seja implementado."""
    raise HTTPException(
        status_code=410,
        detail=(
            "Auto-cadastro desabilitado. Solicite convite ao administrador da "
            "sua empresa."
        ),
    )


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    body: VerifyEmailRequest,
    request: Request,
    session: SessionDep,
) -> MessageResponse:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    try:
        uc = VerifyEmailUseCase(session, redis)
        await uc.execute(
            token=body.token,
            ip=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except InvalidVerifyTokenError:
        raise HTTPException(status_code=400, detail="Token inválido ou expirado")
    finally:
        await redis.aclose()

    return MessageResponse(detail="E-mail verificado com sucesso!")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    body: ResendVerificationRequest,
    session: SessionDep,
) -> MessageResponse:
    settings = get_settings()
    redis = Redis.from_url(settings.REDIS_URL, decode_responses=True)

    if settings.SMTP_HOST:
        from app.infrastructure.adapters.smtp_email_adapter import SmtpEmailAdapter

        email_sender = SmtpEmailAdapter()
    else:
        from app.infrastructure.adapters.console_email_adapter import ConsoleEmailAdapter

        email_sender = ConsoleEmailAdapter()

    try:
        uc = ResendVerificationUseCase(session, redis, email_sender)
        await uc.execute(email=body.email)
    finally:
        await redis.aclose()

    # Always 200 — prevent email enumeration
    return MessageResponse(detail="Se o e-mail existir, um link de verificação foi enviado.")
