"""Explicit tenant authorization over the service-role Supabase client.

The backend's Supabase client can bypass row-level security, so every scoped
lookup must pass through these helpers before returning or mutating tenant data.
Inaccessible and nonexistent resources intentionally share the same 404.
"""

from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any
from uuid import UUID

from fastapi import HTTPException, status

from shared.auth import Principal

logger = logging.getLogger(__name__)

_WRITE_ROLES = frozenset({"editor", "admin"})
_READ_ROLES = frozenset({"viewer", "editor", "admin"})


@dataclass(frozen=True, slots=True)
class ProjectAccess:
    project_id: str
    role: str
    is_owner: bool


@dataclass(frozen=True, slots=True)
class AuthorizedComplianceCheck:
    record: dict[str, Any]
    access: ProjectAccess


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "RESOURCE_NOT_FOUND", "message": "Resource not found"},
    )


def _database_unavailable() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail={
            "code": "DATASTORE_UNAVAILABLE",
            "message": "Service temporarily unavailable",
        },
    )


def _canonical_uuid(value: str) -> str:
    try:
        return str(UUID(str(value)))
    except (TypeError, ValueError, AttributeError):
        raise _not_found()


def _client_from_store(store: Any) -> Any:
    client = getattr(store, "client", None)
    if client is None:
        raise _database_unavailable()
    return client


def require_project_access(
    store: Any,
    project_id: str,
    principal: Principal,
    *,
    write: bool = False,
) -> ProjectAccess:
    """Require owner/member access to a project.

    Owners always have write access. Members require viewer-or-higher for reads
    and editor-or-higher for writes. A denied lookup returns the same response
    as a missing project, preventing tenant enumeration.
    """

    canonical_project_id = _canonical_uuid(project_id)
    client = _client_from_store(store)
    try:
        response = (
            client.table("projects")
            .select("id, owner_email")
            .eq("id", canonical_project_id)
            .limit(1)
            .execute()
        )
        projects = response.data or []
        if not projects:
            raise _not_found()

        owner_email = str(projects[0].get("owner_email") or "").strip().casefold()
        if owner_email and owner_email == principal.email:
            return ProjectAccess(canonical_project_id, "owner", True)

        response = (
            client.table("project_members")
            .select("email, role")
            .eq("project_id", canonical_project_id)
            .eq("email", principal.email)
            .limit(1)
            .execute()
        )
        members = response.data or []
        if not members:
            raise _not_found()
        role = str(members[0].get("role") or "").strip().casefold()
        allowed_roles = _WRITE_ROLES if write else _READ_ROLES
        if role not in allowed_roles:
            raise _not_found()
        return ProjectAccess(canonical_project_id, role, False)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "[Authorization] Project access lookup failed project_id=%s subject=%s",
            canonical_project_id,
            principal.subject,
        )
        raise _database_unavailable()


def get_authorized_compliance_check(
    store: Any,
    task_id: str,
    principal: Principal,
    *,
    write: bool = False,
    fields: str = "*",
) -> AuthorizedComplianceCheck:
    """Resolve a compliance task through its authorized project.

    The task's project is authoritative. The compliance row must match both the
    task and that project, preventing inconsistent or attacker-controlled
    ``project_id`` values from widening access.
    """

    canonical_task_id = _canonical_uuid(task_id)
    client = _client_from_store(store)
    try:
        task_response = (
            client.table("tasks")
            .select("id, project_id, type")
            .eq("id", canonical_task_id)
            .eq("type", "compliance")
            .limit(1)
            .execute()
        )
        tasks = task_response.data or []
        if not tasks:
            raise _not_found()
        project_id = _canonical_uuid(tasks[0].get("project_id"))
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "[Authorization] Task scope lookup failed task_id=%s subject=%s",
            canonical_task_id,
            principal.subject,
        )
        raise _database_unavailable()

    access = require_project_access(store, project_id, principal, write=write)

    try:
        check_response = (
            client.table("compliance_checks")
            .select(fields)
            .eq("task_id", canonical_task_id)
            .eq("project_id", project_id)
            .limit(1)
            .execute()
        )
        checks = check_response.data or []
        if not checks:
            raise _not_found()
        return AuthorizedComplianceCheck(record=dict(checks[0]), access=access)
    except HTTPException:
        raise
    except Exception:
        logger.exception(
            "[Authorization] Compliance lookup failed task_id=%s subject=%s",
            canonical_task_id,
            principal.subject,
        )
        raise _database_unavailable()


__all__ = [
    "AuthorizedComplianceCheck",
    "ProjectAccess",
    "get_authorized_compliance_check",
    "require_project_access",
]
