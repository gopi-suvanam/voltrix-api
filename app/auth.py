import hashlib
import secrets

from fastapi import Depends, HTTPException, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .config import settings

_bearer = HTTPBearer(auto_error=False)


def verify_token(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """
    Validate the Bearer token against the stored SHA-256 hash.
    Auth is skipped entirely when API_TOKEN_HASH is not configured.
    """
    if not settings.api_token_hash:
        return  # auth disabled — development mode

    if credentials is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Bearer token required"},
        )

    incoming_hash = hashlib.sha256(credentials.credentials.encode()).hexdigest()

    # Timing-safe comparison to prevent timing attacks
    if not secrets.compare_digest(incoming_hash, settings.api_token_hash):
        raise HTTPException(
            status_code=401,
            detail={"code": "UNAUTHORIZED", "message": "Invalid Bearer token"},
        )
