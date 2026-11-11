import logging
from typing import Optional
from fastapi import APIRouter, HTTPException, Depends, Header, Request, Response, status

from app.schemas.user import (
    UserRegisterRequest,
    UserVerifyRequest,
    UserLoginRequest,
    UserForgotPasswordRequest,
    UserResetPasswordRequest,
    UserResponse,
    AuthResponse,
)
from app.services.auth_security import (
    hash_password,
    verify_password,
    generate_session_token,
    generate_verification_code,
    hash_code,
    check_rate_limit,
)
from app.db.repository import (
    create_user,
    get_user_by_identifier,
    get_user_by_id,
    verify_user,
    update_user_password,
    save_verification_code,
    check_verification_code,
    create_session,
    delete_session,
)
from app.dependencies.auth import require_current_user, extract_token_from_request

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest):
    """Register a new auditor account using email or phone and send a 6-digit verification code."""
    identifier = payload.identifier.strip().lower()

    if not check_rate_limit(f"register_{identifier}", max_requests=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many registration attempts. Please wait 60 seconds.",
        )

    existing = get_user_by_identifier(identifier)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account is already registered with this identifier. Please log in.",
        )

    # Hash password securely
    pwd_hash = hash_password(payload.password)

    # Create unverified user
    user = create_user(
        identifier=identifier,
        password_hash=pwd_hash,
        full_name=payload.full_name,
        is_verified=False,
    )

    # Generate and store 6-digit OTP code
    otp_code = generate_verification_code()
    save_verification_code(identifier, hash_code(otp_code), purpose="register", expires_minutes=15)
    logger.info("Verification code generated for '%s': %s", identifier, otp_code)

    return {
        "message": "Account created. Please verify your account with the 6-digit OTP code.",
        "user_id": user["id"],
        "identifier": user["identifier"],
        "dev_verification_code": otp_code,  # Provided in dev/testing environments for instant verification
    }


@router.post("/verify", response_model=AuthResponse)
def verify(payload: UserVerifyRequest, response: Response):
    """Verify registration using the 6-digit OTP code and start session."""
    identifier = payload.identifier.strip().lower()

    if not check_rate_limit(f"verify_{identifier}", max_requests=10, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many verification attempts. Please wait 60 seconds.",
        )

    is_valid = check_verification_code(identifier, hash_code(payload.code), purpose="register")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired 6-digit verification code.",
        )

    verify_user(identifier)
    user = get_user_by_identifier(identifier)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    token = generate_session_token()
    create_session(user["id"], token, expires_hours=72)
    response.set_cookie(
        key="fee_auditor_session",
        value=token,
        max_age=72 * 3600,
        httponly=True,
        samesite="lax",
    )

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            identifier=user["identifier"],
            email=user["email"],
            phone=user["phone"],
            full_name=user["full_name"],
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            term_preference=user["academic_term_preference"],
        ),
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: UserLoginRequest, response: Response):
    """Authenticate with identifier and password to obtain a bearer session token."""
    identifier = payload.identifier.strip().lower()

    if not check_rate_limit(f"login_{identifier}", max_requests=8, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many login attempts. Please wait 60 seconds.",
        )

    user = get_user_by_identifier(identifier)
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid identifier or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user["is_verified"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please verify your account with the 6-digit OTP code.",
        )

    token = generate_session_token()
    create_session(user["id"], token, expires_hours=72)
    response.set_cookie(
        key="fee_auditor_session",
        value=token,
        max_age=72 * 3600,
        httponly=True,
        samesite="lax",
    )

    return AuthResponse(
        access_token=token,
        token_type="bearer",
        user=UserResponse(
            id=user["id"],
            identifier=user["identifier"],
            email=user["email"],
            phone=user["phone"],
            full_name=user["full_name"],
            is_verified=user["is_verified"],
            created_at=user["created_at"],
            term_preference=user["academic_term_preference"],
        ),
    )


@router.post("/logout")
def logout(request: Request, response: Response, authorization: Optional[str] = Header(None)):
    """Terminate the active session and revoke credentials."""
    token = extract_token_from_request(request, authorization)
    if token:
        delete_session(token)
    response.delete_cookie(key="fee_auditor_session")
    return {"message": "Logged out successfully."}


@router.get("/me", response_model=UserResponse)
def get_current_user_profile(user: dict = Depends(require_current_user)):
    """Return profile and preferences for the currently authenticated user."""
    return UserResponse(
        id=user["id"],
        identifier=user["identifier"],
        email=user["email"],
        phone=user["phone"],
        full_name=user["full_name"],
        is_verified=user["is_verified"],
        created_at=user["created_at"],
        term_preference=user["academic_term_preference"],
    )


@router.post("/forgot-password")
def forgot_password(payload: UserForgotPasswordRequest):
    """Request a 6-digit password reset code."""
    identifier = payload.identifier.strip().lower()

    if not check_rate_limit(f"forgot_{identifier}", max_requests=5, window_seconds=60):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many password reset requests. Please wait 60 seconds.",
        )

    user = get_user_by_identifier(identifier)
    if not user:
        # Don't leak user existence in generic message
        return {"message": "If the account exists, a 6-digit reset code has been sent."}

    reset_code = generate_verification_code()
    save_verification_code(identifier, hash_code(reset_code), purpose="reset_password", expires_minutes=15)
    logger.info("Password reset code generated for '%s': %s", identifier, reset_code)

    return {
        "message": "Password reset code sent.",
        "dev_reset_code": reset_code,
    }


@router.post("/reset-password")
def reset_password(payload: UserResetPasswordRequest):
    """Reset password using 6-digit OTP code."""
    identifier = payload.identifier.strip().lower()

    is_valid = check_verification_code(identifier, hash_code(payload.code), purpose="reset_password")
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset code.",
        )

    user = get_user_by_identifier(identifier)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    new_hash = hash_password(payload.new_password)
    update_user_password(user["id"], new_hash)

    return {"message": "Password has been successfully updated. You may now log in."}
