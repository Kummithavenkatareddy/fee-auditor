from typing import Optional, Literal
from pydantic import BaseModel, Field, EmailStr


class UserRegisterRequest(BaseModel):
    identifier: str = Field(..., description="Email address or phone number")
    password: str = Field(..., min_length=8, description="Minimum 8 characters password")
    full_name: Optional[str] = Field(None, description="Auditor full name")


class UserVerifyRequest(BaseModel):
    identifier: str = Field(..., description="Email address or phone number")
    code: str = Field(..., min_length=6, max_length=6, description="6-digit verification OTP")


class UserLoginRequest(BaseModel):
    identifier: str = Field(..., description="Email address or phone number")
    password: str = Field(...)


class UserForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., description="Email address or phone number")


class UserResetPasswordRequest(BaseModel):
    identifier: str = Field(..., description="Email address or phone number")
    code: str = Field(..., min_length=6, max_length=6)
    new_password: str = Field(..., min_length=8)


class UserProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    term_preference: Optional[str] = None


class UserPasswordChange(BaseModel):
    current_password: str = Field(...)
    new_password: str = Field(..., min_length=8)


class UserResetDataRequest(BaseModel):
    password: str = Field(..., description="Re-authentication password")
    confirmation_phrase: Literal["RESET"] = Field(..., description="Must type RESET exactly")


class UserDeleteAccountRequest(BaseModel):
    password: str = Field(..., description="Re-authentication password")
    confirmation_phrase: Literal["DELETE"] = Field(..., description="Must type DELETE exactly")


class UserResponse(BaseModel):
    id: str
    identifier: str
    email: Optional[str] = None
    phone: Optional[str] = None
    full_name: Optional[str] = None
    is_verified: bool = False
    created_at: str
    term_preference: Optional[str] = "Fall 2026"


class AuthResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse

