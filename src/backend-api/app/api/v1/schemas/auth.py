from pydantic import BaseModel, EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    id: str
    email: str
    full_name: str
    roles: list[str]
    is_mfa_enabled: bool

    model_config = {"from_attributes": True}


class LoginResponse(BaseModel):
    access_token: str
    user: UserResponse


class MfaRequiredResponse(BaseModel):
    mfa_required: bool = True
    mfa_token: str


class TokenRefreshResponse(BaseModel):
    access_token: str


class MessageResponse(BaseModel):
    detail: str


class ForgotPasswordRequest(BaseModel):
    email: EmailStr


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


class RegisterRequest(BaseModel):
    full_name: str
    email: EmailStr
    password: str
    password_confirmation: str


class VerifyEmailRequest(BaseModel):
    token: str


class ResendVerificationRequest(BaseModel):
    email: EmailStr
