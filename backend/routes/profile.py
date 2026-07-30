"""
routes/profile.py
─────────────────
User + Business profile endpoints.

- GET /api/account/user — Get or create the authenticated user's record
- GET/POST /api/account/profile — Read/write the authenticated user's profile
"""

import logging
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.clients import supabase
from shared.auth import Principal, get_current_principal
from shared.zernio_key_vault import (
    ZernioKeySecurityError,
    decrypt_key,
    encrypt_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profile"])


class BusinessProfileRequest(BaseModel):
    """Request body for creating/updating a business profile."""
    company_name: str
    product_category: str
    product_description: str = ""
    target_platforms: list[str] = []
    target_markets: list[str] = []


# -- User endpoints ------------------------------------------------------------


@router.get("/account/user")
async def get_or_create_user(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Get user record. Creates one if it doesn't exist (first login).

    Returns: { email, is_onboarded }
    """
    try:
        response = supabase.table("users").select("email, is_onboarded").eq("email", principal.email).execute()
        rows = response.data or []

        if rows:
            return JSONResponse(content=rows[0])

        # First time — create user record
        insert_resp = supabase.table("users").insert({"email": principal.email, "is_onboarded": False}).execute()
        if insert_resp.data:
            logger.info("[Profile] Created new user subject=%s", principal.subject)
            return JSONResponse(content=insert_resp.data[0])

        return JSONResponse(content={"email": principal.email, "is_onboarded": False})

    except Exception:
        logger.exception("[Profile] get_or_create_user failed subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "User profile is temporarily unavailable."})


@router.get("/account/onboarding-status")
async def check_onboarding_status(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Quick check: has user completed onboarding? Uses the users table."""
    try:
        response = supabase.table("users").select("is_onboarded").eq("email", principal.email).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(content={"onboarding_complete": False})
        return JSONResponse(content={"onboarding_complete": rows[0].get("is_onboarded", False)})
    except Exception:
        logger.exception("[Profile] Onboarding check failed subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Onboarding status is temporarily unavailable."})


# -- Business Profile endpoints ------------------------------------------------


@router.get("/account/profile")
async def get_profile(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Get a user's business profile."""
    try:
        response = (
            supabase.table("business_profiles")
            .select("*")
            .eq("owner_email", principal.email)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Profile not found"})
        return JSONResponse(content=rows[0])
    except Exception:
        logger.exception("[Profile] Failed to get profile subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Business profile is temporarily unavailable."})


@router.post("/account/profile")
async def create_or_update_profile(
    body: BusinessProfileRequest,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Create/update business profile AND set users.is_onboarded = true."""
    try:
        # Upsert business profile
        profile_data = {
            "owner_email": principal.email,
            "company_name": body.company_name,
            "product_category": body.product_category,
            "product_description": body.product_description,
            "target_platforms": body.target_platforms,
            "target_markets": body.target_markets,
            "onboarding_complete": True,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

        response = (
            supabase.table("business_profiles")
            .upsert(profile_data, on_conflict="owner_email")
            .execute()
        )

        # Mark user as onboarded (upsert in case user record doesn't exist)
        supabase.table("users").upsert({
            "email": principal.email,
            "is_onboarded": True,
        }, on_conflict="email").execute()

        if response.data:
            logger.info("[Profile] Onboarding complete subject=%s", principal.subject)
            return JSONResponse(status_code=200, content=response.data[0])

        return JSONResponse(status_code=500, content={"error": "Upsert returned no data"})

    except Exception:
        logger.exception("[Profile] Failed to save profile subject=%s", principal.subject)
        return JSONResponse(status_code=503, content={"error": "Could not save business profile."})


# ─── Zernio API Key Management ────────────────────────────────────────────────

_USER_ZERNIO_KEYS: dict[str, str] = {}


class ZernioKeyRequest(BaseModel):
    api_key: str


def _get_stored_user_zernio_key(email: str) -> str:
    """Fetch and decrypt a user's Zernio key, migrating legacy plaintext once."""
    if email in _USER_ZERNIO_KEYS:
        return _USER_ZERNIO_KEYS[email]
    try:
        resp = supabase.table("users").select("zernio_api_key").eq("email", email).execute()
        if resp.data and resp.data[0].get("zernio_api_key"):
            key, migrate_legacy_value = decrypt_key(resp.data[0]["zernio_api_key"])
            if migrate_legacy_value:
                supabase.table("users").update({"zernio_api_key": encrypt_key(key)}).eq("email", email).execute()
            _USER_ZERNIO_KEYS[email] = key
            return key
    except ZernioKeySecurityError:
        raise
    except Exception:
        logger.exception("[Zernio] Could not read encrypted key for user")
        pass
    return ""


def _format_zernio_accounts(raw_accounts_data: Any) -> list[dict]:
    """Format raw Zernio accounts API response into displayable channel items."""
    accounts = []
    items = raw_accounts_data
    if isinstance(raw_accounts_data, dict):
        items = raw_accounts_data.get("accounts") or raw_accounts_data.get("data") or []

    icon_map = {
        "tiktok": "🎵",
        "instagram": "📸",
        "youtube": "▶️",
        "facebook": "📘",
        "twitter": "𝕏",
        "x": "𝕏",
        "linkedin": "💼",
    }

    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                platform = str(item.get("platform") or item.get("name") or "Social").lower()
                label = item.get("label") or item.get("username") or platform.title()
                accounts.append({
                    "name": label,
                    "icon": icon_map.get(platform, "🔗"),
                    "status": "Active",
                })
    return accounts


@router.get("/user/zernio/connection")
async def get_user_zernio_status(
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Get the authenticated user's Zernio connection status.

    The owner is derived from the verified Cognito identity.  Never accept an
    email in this endpoint: doing so would allow one signed-in user to query
    or overwrite another user's publishing connection.
    """
    try:
        key = _get_stored_user_zernio_key(principal.email)
    except ZernioKeySecurityError as exc:
        logger.error("[Zernio] Secure key storage unavailable while reading connection: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": "Secure Zernio key storage is temporarily unavailable.",
                "code": "zernio_key_storage_unavailable",
            },
        )

    if not key:
        return JSONResponse(content={
            "has_key": False,
            "masked_key": "",
            "connected": False,
            "accounts": [],
            "message": "No Zernio API Key configured.",
        })

    masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"

    # Query live Zernio connected accounts
    accounts = []
    try:
        from shared.zernio_client import get_connected_accounts
        zern_resp = await get_connected_accounts(key)
        accounts = _format_zernio_accounts(zern_resp)
    except Exception as e:
        logger.warning("[Zernio] Failed to fetch connected accounts with user key: %s", e)

    return JSONResponse(content={
        "has_key": True,
        "masked_key": masked,
        "connected": True,
        "accounts": accounts,
        "message": "Zernio account connected.",
    })


@router.post("/user/zernio/connection")
async def save_user_zernio_key(
    body: ZernioKeyRequest,
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Save the authenticated user's Zernio API key and fetch live accounts."""
    raw_key = body.api_key.strip()
    if not raw_key:
        return JSONResponse(status_code=400, content={"error": "API key cannot be empty"})

    # Encrypt before persistence.  The plaintext lives only for the duration
    # of this request and in the short-lived in-process cache used for Zernio.
    _USER_ZERNIO_KEYS[principal.email] = raw_key
    try:
        supabase.table("users").upsert({
            "email": principal.email,
            "zernio_api_key": encrypt_key(raw_key),
        }, on_conflict="email").execute()
    except ZernioKeySecurityError as exc:
        _USER_ZERNIO_KEYS.pop(principal.email, None)
        logger.error("[Zernio] Secure key storage unavailable while saving connection: %s", exc)
        return JSONResponse(
            status_code=503,
            content={
                "error": "Secure Zernio key storage is temporarily unavailable.",
                "code": "zernio_key_storage_unavailable",
            },
        )
    except Exception as e:
        _USER_ZERNIO_KEYS.pop(principal.email, None)
        logger.exception("[Zernio] Failed to persist encrypted user key")
        return JSONResponse(status_code=503, content={"error": "Could not securely save the Zernio API key."})

    masked = raw_key[:6] + "..." + raw_key[-4:] if len(raw_key) > 10 else "***"

    accounts = []
    try:
        from shared.zernio_client import get_connected_accounts
        zern_resp = await get_connected_accounts(raw_key)
        accounts = _format_zernio_accounts(zern_resp)
    except Exception as e:
        logger.warning("[Zernio] Key saved but account lookup failed: %s", e)

    return JSONResponse(content={
        "status": "connected",
        "message": "Zernio API Key saved successfully! Your Zernio account is connected.",
        "has_key": True,
        "masked_key": masked,
        "connected": True,
        "accounts": accounts,
    })


@router.delete("/user/zernio/connection")
async def delete_user_zernio_key(
    principal: Principal = Depends(get_current_principal),
) -> JSONResponse:
    """Remove the authenticated user's Zernio API key."""
    if principal.email in _USER_ZERNIO_KEYS:
        del _USER_ZERNIO_KEYS[principal.email]
    try:
        supabase.table("users").update({"zernio_api_key": None}).eq("email", principal.email).execute()
    except Exception:
        pass
    return JSONResponse(content={
        "status": "disconnected",
        "has_key": False,
        "connected": False,
        "masked_key": "",
        "accounts": [],
        "message": "Zernio API key removed.",
    })


