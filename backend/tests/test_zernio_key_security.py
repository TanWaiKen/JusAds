from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from cryptography.fernet import Fernet

from routes import profile, statistics
from shared.auth import Principal
from shared import zernio_key_vault as vault


@pytest.fixture(autouse=True)
def encryption_key(monkeypatch):
    monkeypatch.setattr(vault, "ZERNIO_KEY_ENCRYPTION_KEY", Fernet.generate_key().decode())
    vault.reset_key_cache()
    profile._USER_ZERNIO_KEYS.clear()
    yield
    vault.reset_key_cache()
    profile._USER_ZERNIO_KEYS.clear()


def test_zernio_key_ciphertext_never_contains_plaintext():
    stored = vault.encrypt_key("zern_live_sensitive_value")

    assert stored.startswith("fernet:v1:")
    assert "zern_live_sensitive_value" not in stored
    assert vault.decrypt_key(stored) == ("zern_live_sensitive_value", False)


def test_zernio_key_storage_fails_closed_without_encryption_key(monkeypatch):
    monkeypatch.setattr(vault, "ZERNIO_KEY_ENCRYPTION_KEY", "")
    vault.reset_key_cache()

    with pytest.raises(vault.ZernioKeySecurityError):
        vault.encrypt_key("zern_live_sensitive_value")


class _Query:
    def __init__(self, parent):
        self.parent = parent

    def select(self, _fields): return self
    def eq(self, _field, _value): return self
    def update(self, payload):
        self.parent.updated = payload
        return self
    def execute(self): return SimpleNamespace(data=[{"zernio_api_key": self.parent.value}])


class _Supabase:
    def __init__(self, value):
        self.value = value
        self.updated = None

    def table(self, _name): return _Query(self)


def test_legacy_plaintext_key_is_migrated_on_first_read(monkeypatch):
    fake_db = _Supabase("zern_live_old_key")
    monkeypatch.setattr(profile, "supabase", fake_db)

    assert profile._get_stored_user_zernio_key("owner@example.com") == "zern_live_old_key"
    assert fake_db.updated is not None
    assert fake_db.updated["zernio_api_key"].startswith("fernet:v1:")


def test_statistics_uses_verified_principal_not_email_query(monkeypatch):
    principal = Principal("subject-1", "owner@example.com", {})
    seen = []

    def stored_key(email):
        seen.append(email)
        return "decrypted-key"

    async def overview(*, api_key):
        assert api_key == "decrypted-key"
        return {"source": "zernio"}

    monkeypatch.setattr(statistics, "_get_stored_user_zernio_key", stored_key)
    monkeypatch.setattr(statistics, "get_overall_analytics", overview)

    response = asyncio.run(statistics.get_statistics_overview(principal))
    assert response.status_code == 200
    assert seen == ["owner@example.com"]
