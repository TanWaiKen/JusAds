"""Focused tests for Cognito verification and tenant authorization helpers."""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import Mock, patch
from uuid import uuid4

from fastapi import HTTPException
from jwt import InvalidTokenError, PyJWKClientError
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.auth import Principal, verify_cognito_id_token
from shared.authorization import (
    get_authorized_compliance_check,
    require_project_access,
)


ISSUER = "https://cognito-idp.example.test/pool"
CLIENT_ID = "client-id"


def _valid_claims(**overrides):
    claims = {
        "sub": "immutable-user-id",
        "email": "Owner@Example.com",
        "email_verified": True,
        "token_use": "id",
        "aud": CLIENT_ID,
        "iat": 1,
        "exp": 9999999999,
    }
    claims.update(overrides)
    return claims


def test_verified_id_token_produces_normalized_principal() -> None:
    jwks = Mock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key="public-key")
    with patch("shared.auth._jwks_client", return_value=jwks), patch(
        "shared.auth.jwt.decode", return_value=_valid_claims()
    ) as decode:
        principal = verify_cognito_id_token(
            "signed-token", issuer=ISSUER, client_id=CLIENT_ID
        )

    assert principal.subject == "immutable-user-id"
    assert principal.email == "owner@example.com"
    decode.assert_called_once_with(
        "signed-token",
        "public-key",
        algorithms=["RS256"],
        audience=CLIENT_ID,
        issuer=ISSUER,
        options={"require": ["exp", "iat", "sub", "aud"]},
    )


@pytest.mark.parametrize(
    "claims",
    [
        _valid_claims(token_use="access"),
        _valid_claims(email_verified=False),
        _valid_claims(email=""),
        _valid_claims(sub=""),
    ],
)
def test_wrong_token_type_or_identity_claims_are_rejected(claims: dict) -> None:
    jwks = Mock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key="public-key")
    with patch("shared.auth._jwks_client", return_value=jwks), patch(
        "shared.auth.jwt.decode", return_value=claims
    ), pytest.raises(HTTPException) as exc:
        verify_cognito_id_token("signed-token", issuer=ISSUER, client_id=CLIENT_ID)

    assert exc.value.status_code == 401
    assert exc.value.detail == {
        "code": "AUTH_INVALID",
        "message": "Invalid or expired authentication token",
    }


def test_invalid_signature_returns_stable_unauthorized_error() -> None:
    jwks = Mock()
    jwks.get_signing_key_from_jwt.return_value = SimpleNamespace(key="public-key")
    with patch("shared.auth._jwks_client", return_value=jwks), patch(
        "shared.auth.jwt.decode", side_effect=InvalidTokenError("sensitive detail")
    ), pytest.raises(HTTPException) as exc:
        verify_cognito_id_token("bad-token", issuer=ISSUER, client_id=CLIENT_ID)

    assert exc.value.status_code == 401
    assert "sensitive detail" not in str(exc.value.detail)
    assert exc.value.detail["code"] == "AUTH_INVALID"


def test_unknown_signing_key_returns_stable_unauthorized_error() -> None:
    jwks = Mock()
    jwks.get_signing_key_from_jwt.side_effect = PyJWKClientError("unknown key id")
    with patch("shared.auth._jwks_client", return_value=jwks), pytest.raises(
        HTTPException
    ) as exc:
        verify_cognito_id_token("bad-token", issuer=ISSUER, client_id=CLIENT_ID)

    assert exc.value.status_code == 401
    assert exc.value.detail["code"] == "AUTH_INVALID"
    assert "unknown key id" not in str(exc.value.detail)


def test_jwks_provider_failure_returns_stable_service_error() -> None:
    jwks = Mock()
    jwks.get_signing_key_from_jwt.side_effect = RuntimeError("provider secret")
    with patch("shared.auth._jwks_client", return_value=jwks), pytest.raises(
        HTTPException
    ) as exc:
        verify_cognito_id_token("token", issuer=ISSUER, client_id=CLIENT_ID)

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "AUTH_SERVICE_UNAVAILABLE"
    assert "provider secret" not in str(exc.value.detail)


class _FakeQuery:
    def __init__(self, client: "_FakeClient", table: str):
        self.client = client
        self.table = table
        self.filters: list[tuple[str, object]] = []

    def select(self, _fields: str) -> "_FakeQuery":
        return self

    def eq(self, field: str, value: object) -> "_FakeQuery":
        self.filters.append((field, value))
        return self

    def limit(self, _limit: int) -> "_FakeQuery":
        return self

    def execute(self):
        if self.client.failure:
            raise RuntimeError("database provider detail")
        rows = self.client.tables.get(self.table, [])
        filtered = [
            dict(row)
            for row in rows
            if all(str(row.get(field)) == str(value) for field, value in self.filters)
        ]
        return SimpleNamespace(data=filtered)


class _FakeClient:
    def __init__(self, tables: dict[str, list[dict]], *, failure: bool = False):
        self.tables = tables
        self.failure = failure

    def table(self, name: str) -> _FakeQuery:
        return _FakeQuery(self, name)


class _FakeStore:
    def __init__(self, tables: dict[str, list[dict]], *, failure: bool = False):
        self.client = _FakeClient(tables, failure=failure)


def _tenant_fixture():
    project_id = str(uuid4())
    task_id = str(uuid4())
    tables = {
        "projects": [
            {
                "id": project_id,
                "owner_email": "owner@example.com",
            }
        ],
        "project_members": [
            {"project_id": project_id, "email": "viewer@example.com", "role": "viewer"},
            {"project_id": project_id, "email": "editor@example.com", "role": "editor"},
        ],
        "tasks": [
            {
                "id": task_id,
                "project_id": project_id,
                "type": "compliance",
            }
        ],
        "compliance_checks": [
            {
                "task_id": task_id,
                "project_id": project_id,
                "status": "checked",
            }
        ],
    }
    return project_id, task_id, tables


def _principal(email: str) -> Principal:
    return Principal("sub-" + email, email, {"sub": "sub-" + email, "email": email})


def test_owner_and_member_roles_are_enforced() -> None:
    project_id, task_id, tables = _tenant_fixture()
    store = _FakeStore(tables)

    owner = require_project_access(store, project_id, _principal("owner@example.com"), write=True)
    viewer = require_project_access(store, project_id, _principal("viewer@example.com"))
    editor_check = get_authorized_compliance_check(
        store, task_id, _principal("editor@example.com"), write=True
    )

    assert owner.is_owner is True
    assert viewer.role == "viewer"
    assert editor_check.record["task_id"] == task_id
    assert editor_check.access.role == "editor"


def test_viewer_cannot_mutate_and_other_tenant_cannot_read() -> None:
    project_id, task_id, tables = _tenant_fixture()
    store = _FakeStore(tables)

    with pytest.raises(HTTPException) as viewer_exc:
        require_project_access(
            store, project_id, _principal("viewer@example.com"), write=True
        )
    with pytest.raises(HTTPException) as tenant_exc:
        get_authorized_compliance_check(
            store, task_id, _principal("other@example.com")
        )

    assert viewer_exc.value.status_code == 404
    assert tenant_exc.value.status_code == 404
    assert viewer_exc.value.detail == tenant_exc.value.detail


def test_missing_and_inaccessible_tasks_are_indistinguishable() -> None:
    _, task_id, tables = _tenant_fixture()
    store = _FakeStore(tables)

    with pytest.raises(HTTPException) as inaccessible:
        get_authorized_compliance_check(
            store, task_id, _principal("other@example.com")
        )
    with pytest.raises(HTTPException) as missing:
        get_authorized_compliance_check(
            store, str(uuid4()), _principal("other@example.com")
        )

    assert inaccessible.value.status_code == missing.value.status_code == 404
    assert inaccessible.value.detail == missing.value.detail


def test_check_must_match_authorized_tasks_project() -> None:
    _, task_id, tables = _tenant_fixture()
    tables["compliance_checks"][0]["project_id"] = str(uuid4())

    with pytest.raises(HTTPException) as exc:
        get_authorized_compliance_check(
            _FakeStore(tables), task_id, _principal("owner@example.com")
        )

    assert exc.value.status_code == 404
    assert exc.value.detail["code"] == "RESOURCE_NOT_FOUND"


def test_database_errors_do_not_leak_provider_details() -> None:
    project_id, _, tables = _tenant_fixture()
    with pytest.raises(HTTPException) as exc:
        require_project_access(
            _FakeStore(tables, failure=True),
            project_id,
            _principal("owner@example.com"),
        )

    assert exc.value.status_code == 503
    assert exc.value.detail["code"] == "DATASTORE_UNAVAILABLE"
    assert "database provider detail" not in str(exc.value.detail)
