from typing import Optional
from fastapi import Request, Header, HTTPException, status
from app.db.repository import get_session_user, get_user_by_id
from app.schemas.user import UserResponse

SYSTEM_DEFAULT_USER = {
    "id": "system_default",
    "identifier": "auditor@university.edu",
    "email": "auditor@university.edu",
    "phone": "+91 98765 43210",
    "full_name": "Accounts Officer",
    "is_verified": True,
    "created_at": "2026-08-01T00:00:00Z",
    "academic_term_preference": "Fall 2026",
}


def extract_token_from_request(request: Request, authorization: Optional[str] = None) -> Optional[str]:
    """Extract token from Authorization: Bearer <token> header or fee_auditor_session cookie."""
    if authorization:
        parts = authorization.split()
        if len(parts) == 2 and parts[0].lower() == "bearer":
            return parts[1].strip()
        if len(parts) == 1 and parts[0]:
            return parts[0].strip()

    # Check cookies
    if request and hasattr(request, "cookies"):
        cookie_token = request.cookies.get("fee_auditor_session")
        if cookie_token:
            return cookie_token.strip()

    return None


def extract_bearer_token(authorization: Optional[str]) -> Optional[str]:
    """Legacy helper for extracting bearer token from header."""
    if not authorization:
        return None
    parts = authorization.split()
    if len(parts) == 2 and parts[0].lower() == "bearer":
        return parts[1]
    return None


async def get_optional_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> Optional[dict]:
    """
    Returns authenticated user if bearer token or cookie is provided and valid.
    Returns None if unauthenticated (never leaks SYSTEM_DEFAULT_USER).
    """
    token = extract_token_from_request(request, authorization)
    if token:
        user = get_session_user(token)
        if user:
            return user
    return None


async def require_current_user(
    request: Request,
    authorization: Optional[str] = Header(None),
) -> dict:
    """
    Strictly requires an authenticated user session.
    Inspects Authorization: Bearer <token> and Cookie: fee_auditor_session.
    Raises 401 Unauthorized if no valid session token is provided.
    """
    token = extract_token_from_request(request, authorization)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please log in to access this resource.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = get_session_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session token. Please log in again.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

