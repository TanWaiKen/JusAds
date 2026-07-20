"""
routes/health.py
────────────────
Health check endpoint.
"""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api", tags=["health"])

# Set during app startup
_s3_available = False
_supabase_available = False


def init_health(s3_ok: bool, supabase_ok: bool):
    global _s3_available, _supabase_available
    _s3_available = s3_ok
    _supabase_available = supabase_ok


@router.get("/health")
async def health() -> JSONResponse:
    """Health check."""
    return JSONResponse(content={
        "status": "ok",
        "services": {
            "s3": _s3_available,
            "supabase": _supabase_available,
        },
    })
