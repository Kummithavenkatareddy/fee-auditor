import logging
from fastapi import APIRouter, HTTPException, Depends, status

from app.schemas.user import (
    UserProfileUpdate,
    UserPasswordChange,
    UserResetDataRequest,
    UserDeleteAccountRequest,
    UserResponse,
)
from app.services.auth_security import hash_password, verify_password
from app.db.repository import (
    update_user_profile,
    update_user_password,
    reset_user_data,
    delete_user_account,
    get_user_by_id,
)
from app.dependencies.auth import require_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/users", tags=["User Settings & Account Management"])


@router.patch("/profile", response_model=UserResponse)
def update_profile(
    payload: UserProfileUpdate,
    current_user: dict = Depends(require_current_user),
):
    """Update user profile name and academic term preferences."""
    updated = update_user_profile(
        user_id=current_user["id"],
        full_name=payload.full_name,
        term_pref=payload.term_preference,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    return UserResponse(
        id=updated["id"],
        identifier=updated["identifier"],
        email=updated["email"],
        phone=updated["phone"],
        full_name=updated["full_name"],
        is_verified=updated["is_verified"],
        created_at=updated["created_at"],
        term_preference=updated["academic_term_preference"],
    )


@router.post("/change-password")
def change_password(
    payload: UserPasswordChange,
    current_user: dict = Depends(require_current_user),
):
    """Change account password with verification of the current password."""
    # Re-fetch user to get latest password hash
    user = get_user_by_id(current_user["id"])
    if not user or not verify_password(payload.current_password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password verification failed.",
        )

    new_hash = hash_password(payload.new_password)
    update_user_password(current_user["id"], new_hash)
    logger.info("Password successfully changed for user '%s'", current_user["id"])
    return {"message": "Password changed successfully."}


@router.post("/reset-data")
def reset_my_data(
    payload: UserResetDataRequest,
    current_user: dict = Depends(require_current_user),
):
    """
    Destructive Operation: Reset My Data.
    Requires password re-authentication and typed phrase 'RESET'.
    Deletes all documents, extracted line items, flags, and storage files for this user.
    Keeps user account and profile intact.
    """
    if payload.confirmation_phrase != "RESET":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase must be exactly 'RESET'.",
        )

    user = get_user_by_id(current_user["id"])
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password re-authentication failed.",
        )

    deleted_count = reset_user_data(current_user["id"])
    logger.warning("User '%s' executed Reset My Data (deleted %d documents)", current_user["id"], deleted_count)
    return {
        "message": f"All data reset successfully. Deleted {deleted_count} documents and associated files.",
        "deleted_documents": deleted_count,
    }


@router.delete("/account")
def delete_my_account(
    payload: UserDeleteAccountRequest,
    current_user: dict = Depends(require_current_user),
):
    """
    Destructive Operation: Delete Account.
    Requires password re-authentication and typed phrase 'DELETE'.
    Permanently purges user account, sessions, documents, and all storage files.
    """
    if payload.confirmation_phrase != "DELETE":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Confirmation phrase must be exactly 'DELETE'.",
        )

    user = get_user_by_id(current_user["id"])
    if not user or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password re-authentication failed.",
        )

    success = delete_user_account(current_user["id"])
    if not success:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to purge account.")

    logger.warning("User account '%s' permanently deleted.", current_user["id"])
    return {"message": "Account and all associated documents permanently deleted."}

