"""Cognito bearer-token authentication for backend API routes.

Only signed Cognito ID tokens issued to this application's client are accepted.
The verified ``sub`` is the immutable user identifier; the verified email is
retained solely for compatibility with the current project ownership schema.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import logging
from typing import Annotated, Any

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError, PyJWKClient, PyJWKClientConnectionError, PyJWTError

from shared.config import COGNITO_CLIENT_ID, COGNITO_ISSUER

logger = logging.getLogger(__name__)

_bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True, slots=True)
class Principal:
    """Identity derived exclusively from a verified Cognito ID token."""

    subject: str
    email: str
    claims: dict[str, Any]

    @property
    def user_id(self) -> str:
        """Compatibility alias for callers that name Cognito ``sub`` user_id."""

        return self.subject


def _public_auth_error(code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": code, "message": message},
        headers={"WWW-Authenticate": "Bearer"},
    )


def _auth_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "AUTH_SERVICE_UNAVAILABLE",
            "message": "Authentication service is temporarily unavailable",
        },
    )


@lru_cache(maxsize=4)
def _jwks_client(issuer: str) -> PyJWKClient:
    """Return a cached JWKS client for one explicitly trusted issuer."""

    return PyJWKClient(
        f"{issuer}/.well-known/jwks.json",
        cache_jwk_set=True,
        lifespan=3600,
    )


def verify_cognito_id_token(
    token: str,
    *,
    issuer: str | None = None,
    client_id: str | None = None,
) -> Principal:
    """Verify a Cognito ID token and return its security principal.

    Signature, issuer, audience, expiry, token type, immutable subject, and
    verified email are all mandatory. Caller-provided identity fields never
    participate in this decision.
    """

    trusted_issuer = (issuer if issuer is not None else COGNITO_ISSUER).strip().rstrip("/")
    trusted_client = (client_id if client_id is not None else COGNITO_CLIENT_ID).strip()
    if not trusted_issuer or not trusted_client:
        logger.error("[Auth] Cognito issuer/client configuration is missing")
        raise _auth_unavailable()
    if not token or not token.strip():
        raise _public_auth_error("AUTH_REQUIRED", "Authentication required")

    try:
        signing_key = _jwks_client(trusted_issuer).get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=trusted_client,
            issuer=trusted_issuer,
            options={"require": ["exp", "iat", "sub", "aud"]},
        )
    except PyJWKClientConnectionError:
        logger.exception("[Auth] Cognito JWKS endpoint unavailable")
        raise _auth_unavailable()
    except (InvalidTokenError, PyJWTError):
        logger.info("[Auth] Rejected invalid Cognito ID token")
        raise _public_auth_error("AUTH_INVALID", "Invalid or expired authentication token")
    except HTTPException:
        raise
    except Exception:
        # JWKS retrieval and key-provider errors are operational failures. Do
        # not expose provider details or incorrectly present them as bad user
        # credentials.
        logger.exception("[Auth] Cognito JWKS verification unavailable")
        raise _auth_unavailable()

    if claims.get("token_use") != "id":
        raise _public_auth_error("AUTH_INVALID", "Invalid or expired authentication token")

    subject = claims.get("sub")
    email = claims.get("email")
    email_verified = claims.get("email_verified")
    if (
        not isinstance(subject, str)
        or not subject.strip()
        or not isinstance(email, str)
        or not email.strip()
        or email_verified not in (True, "true")
    ):
        raise _public_auth_error("AUTH_INVALID", "Invalid or expired authentication token")

    return Principal(
        subject=subject.strip(),
        email=email.strip().casefold(),
        claims=dict(claims),
    )


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> Principal:
    """FastAPI dependency requiring a valid Cognito bearer ID token."""

    if credentials is None or credentials.scheme.casefold() != "bearer":
        raise _public_auth_error("AUTH_REQUIRED", "Authentication required")
    return verify_cognito_id_token(credentials.credentials)


__all__ = ["Principal", "get_current_principal", "verify_cognito_id_token"]
