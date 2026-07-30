"""Application-level encryption for user-provided Zernio API keys.

Supabase RLS protects the database API boundary, but a database export or a
privileged-console mistake must not expose usable third-party publishing keys.
The deployment supplies a distinct Fernet key through its secret manager.
"""

from __future__ import annotations

from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from shared.config import ZERNIO_KEY_ENCRYPTION_KEY

_PREFIX = "fernet:v1:"


class ZernioKeySecurityError(RuntimeError):
    """Raised when secure key storage is unavailable or the ciphertext is invalid."""


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = ZERNIO_KEY_ENCRYPTION_KEY.strip().encode("ascii")
    if not key:
        raise ZernioKeySecurityError(
            "Zernio key storage is unavailable: configure ZERNIO_KEY_ENCRYPTION_KEY."
        )
    try:
        return Fernet(key)
    except (TypeError, ValueError) as exc:
        raise ZernioKeySecurityError(
            "Zernio key storage is unavailable: ZERNIO_KEY_ENCRYPTION_KEY is invalid."
        ) from exc


def encryption_ready() -> bool:
    try:
        _fernet()
        return True
    except ZernioKeySecurityError:
        return False


def encrypt_key(raw_key: str) -> str:
    value = raw_key.strip()
    if not value:
        raise ValueError("Zernio API key cannot be empty")
    return _PREFIX + _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_key(stored_value: str) -> tuple[str, bool]:
    """Return plaintext and whether a legacy plaintext value should be migrated."""
    value = (stored_value or "").strip()
    if not value:
        return "", False
    fernet = _fernet()
    if not value.startswith(_PREFIX):
        # One-time migration path for existing user keys.  It is intentionally
        # unavailable without the configured encryption key, so production does
        # not silently continue to rely on plaintext database secrets.
        return value, True
    try:
        return fernet.decrypt(value[len(_PREFIX):].encode("ascii")).decode("utf-8"), False
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise ZernioKeySecurityError("Stored Zernio connection could not be decrypted.") from exc


def reset_key_cache() -> None:
    """Test helper for deployments that rotate the encryption-key environment."""
    _fernet.cache_clear()
