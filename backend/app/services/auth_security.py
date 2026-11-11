import os
import secrets
import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Dict, Tuple, Optional

# PBKDF2 parameters
SALT_SIZE = 16
HASH_ITERATIONS = 100_000

# In-memory sliding window rate limiter
_RATE_LIMIT_BUCKET: Dict[str, list[float]] = {}


def hash_password(password: str) -> str:
    """Hash password using standard PBKDF2-HMAC-SHA256 with a random salt."""
    salt = secrets.token_bytes(SALT_SIZE)
    key = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, HASH_ITERATIONS)
    return f"{salt.hex()}:{key.hex()}"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against salt:key format."""
    try:
        salt_hex, key_hex = hashed_password.split(":")
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
        key = hashlib.pbkdf2_hmac("sha256", plain_password.encode("utf-8"), salt, HASH_ITERATIONS)
        return secrets.compare_digest(key, expected_key)
    except Exception:
        return False


def generate_session_token() -> str:
    """Generate cryptographically secure session token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash session token using SHA-256 for secure database lookup."""
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


# Fixed demo verification code — used in demo/evaluation mode instead of random OTP.
# This code is NEVER returned in API responses or logged at INFO level in production.
DEMO_VERIFICATION_CODE = "927824"


def generate_verification_code(demo_mode: bool = False) -> str:
    """
    Generate 6-digit numeric verification OTP.
    In demo mode, returns the fixed institutional demo code instead of a random one.
    The fixed code is stored hashed in the database and never sent in API responses.
    """
    if demo_mode:
        return DEMO_VERIFICATION_CODE
    return f"{secrets.randbelow(900000) + 100000}"


def hash_code(code: str) -> str:
    """Hash one-time code for secure database persistence."""
    return hashlib.sha256(code.strip().encode("utf-8")).hexdigest()


def check_rate_limit(key: str, max_requests: int = 5, window_seconds: int = 60) -> bool:
    """
    Check if an action exceeds rate limits using in-memory sliding window.
    Returns True if permitted, False if rate limited.
    """
    now = time.time()
    timestamps = _RATE_LIMIT_BUCKET.setdefault(key, [])
    # Filter out timestamps outside window
    timestamps = [t for t in timestamps if now - t < window_seconds]
    _RATE_LIMIT_BUCKET[key] = timestamps

    if len(timestamps) >= max_requests:
        return False

    timestamps.append(now)
    return True


def reset_rate_limits():
    """Clear all rate limit records (useful for test isolation)."""
    _RATE_LIMIT_BUCKET.clear()
