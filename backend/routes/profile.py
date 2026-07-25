"""
routes/profile.py
─────────────────
User + Business profile endpoints.

- GET /api/user/{email} — Get or create user record, returns is_onboarded
- POST /api/profile — Save business profile + set is_onboarded=true on users table
- GET /api/profile/{email} — Get business profile details
"""

import logging
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from shared.clients import supabase

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["profile"])


class BusinessProfileRequest(BaseModel):
    """Request body for creating/updating a business profile."""
    owner_email: str
    company_name: str
    product_category: str
    product_description: str = ""
    target_platforms: list[str] = []
    target_markets: list[str] = []


# -- User endpoints ------------------------------------------------------------


@router.get("/user/{email}")
async def get_or_create_user(email: str) -> JSONResponse:
    """Get user record. Creates one if it doesn't exist (first login).

    Returns: { email, is_onboarded }
    """
    try:
        response = supabase.table("users").select("*").eq("email", email).execute()
        rows = response.data or []

        if rows:
            return JSONResponse(content=rows[0])

        # First time — create user record
        insert_resp = supabase.table("users").insert({"email": email, "is_onboarded": False}).execute()
        if insert_resp.data:
            logger.info("[Profile] Created new user: %s", email)
            return JSONResponse(content=insert_resp.data[0])

        return JSONResponse(content={"email": email, "is_onboarded": False})

    except Exception as e:
        logger.error("[Profile] get_or_create_user failed for %s: %s", email, e)
        return JSONResponse(content={"email": email, "is_onboarded": False})


@router.get("/profile/{email}/onboarding-status")
async def check_onboarding_status(email: str) -> JSONResponse:
    """Quick check: has user completed onboarding? Uses the users table."""
    try:
        response = supabase.table("users").select("is_onboarded").eq("email", email).execute()
        rows = response.data or []
        if not rows:
            return JSONResponse(content={"onboarding_complete": False})
        return JSONResponse(content={"onboarding_complete": rows[0].get("is_onboarded", False)})
    except Exception as e:
        logger.error("[Profile] Onboarding check failed for %s: %s", email, e)
        return JSONResponse(content={"onboarding_complete": False})


# -- Business Profile endpoints ------------------------------------------------


@router.get("/profile/{email}")
async def get_profile(email: str) -> JSONResponse:
    """Get a user's business profile."""
    try:
        response = (
            supabase.table("business_profiles")
            .select("*")
            .eq("owner_email", email)
            .execute()
        )
        rows = response.data or []
        if not rows:
            return JSONResponse(status_code=404, content={"error": "Profile not found"})
        return JSONResponse(content=rows[0])
    except Exception as e:
        logger.error("[Profile] Failed to get profile for %s: %s", email, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.post("/profile")
async def create_or_update_profile(body: BusinessProfileRequest) -> JSONResponse:
    """Create/update business profile AND set users.is_onboarded = true."""
    try:
        # Upsert business profile
        profile_data = {
            "owner_email": body.owner_email,
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
            "email": body.owner_email,
            "is_onboarded": True,
        }, on_conflict="email").execute()

        if response.data:
            logger.info("[Profile] Onboarding complete for %s", body.owner_email)
            return JSONResponse(status_code=200, content=response.data[0])

        return JSONResponse(status_code=500, content={"error": "Upsert returned no data"})

    except Exception as e:
        logger.error("[Profile] Failed to save profile for %s: %s", body.owner_email, e)
        return JSONResponse(status_code=500, content={"error": str(e)})


# ─── Zernio API Key Management ────────────────────────────────────────────────

_USER_ZERNIO_KEYS: dict[str, str] = {}


class ZernioKeyRequest(BaseModel):
    api_key: str


def _get_stored_user_zernio_key(email: str) -> str:
    """Fetch stored Zernio key from memory or Supabase users table."""
    if email in _USER_ZERNIO_KEYS:
        return _USER_ZERNIO_KEYS[email]
    try:
        resp = supabase.table("users").select("zernio_api_key").eq("email", email).execute()
        if resp.data and resp.data[0].get("zernio_api_key"):
            key = resp.data[0]["zernio_api_key"]
            _USER_ZERNIO_KEYS[email] = key
            return key
    except Exception:
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


@router.get("/user/{email}/zernio")
async def get_user_zernio_status(email: str) -> JSONResponse:
    """Get status of user's configured Zernio API key (default = NOT CONNECTED)."""
    key = _get_stored_user_zernio_key(email)

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


@router.post("/user/{email}/zernio")
async def save_user_zernio_key(email: str, body: ZernioKeyRequest) -> JSONResponse:
    """Save user's Zernio API key to DB and fetch live connected accounts."""
    raw_key = body.api_key.strip()
    if not raw_key:
        return JSONResponse(status_code=400, content={"error": "API key cannot be empty"})

    # Store in-memory and attempt DB persistence
    _USER_ZERNIO_KEYS[email] = raw_key
    try:
        supabase.table("users").upsert({
            "email": email,
            "zernio_api_key": raw_key,
        }, on_conflict="email").execute()
    except Exception as e:
        logger.warning("[Zernio] Failed to persist key to users table (column might be missing): %s", e)

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


@router.delete("/user/{email}/zernio")
async def delete_user_zernio_key(email: str) -> JSONResponse:
    """Remove user's Zernio API key."""
    if email in _USER_ZERNIO_KEYS:
        del _USER_ZERNIO_KEYS[email]
    try:
        supabase.table("users").update({"zernio_api_key": None}).eq("email", email).execute()
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


