"""
routes/profile.py
─────────────────
User + Business profile endpoints.

- GET /api/user/{email} — Get or create user record, returns is_onboarded
- POST /api/profile — Save business profile + set is_onboarded=true on users table
- GET /api/profile/{email} — Get business profile details
"""

import logging
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


# ── User endpoints ────────────────────────────────────────────────────────────


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


# ── Business Profile endpoints ────────────────────────────────────────────────


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
