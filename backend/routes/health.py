"""Liveness and dependency-readiness endpoints for the JusAds API."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])

_s3_available = False
_supabase_available = False


def init_health(s3_ok: bool, supabase_ok: bool) -> None:
    """Record dependency initialization results for readiness reporting."""
    global _s3_available, _supabase_available
    _s3_available = s3_ok
    _supabase_available = supabase_ok


@router.get("/health")
async def liveness() -> JSONResponse:
    """Report that the API process is alive without testing dependencies."""
    return JSONResponse(content={"status": "ok"})


@router.get("/api/health")
async def health() -> JSONResponse:
    """Report API health and startup-time dependency availability."""
    status = "ok" if _supabase_available and _s3_available else "degraded"
    return JSONResponse(content={
        "status": status,
        "services": {"s3": _s3_available, "supabase": _supabase_available},
    })


@router.get("/api/ready")
async def readiness() -> JSONResponse:
    """Return 503 until the required persistence dependency is available."""
    ready = _supabase_available
    return JSONResponse(
        status_code=200 if ready else 503,
        content={
            "status": "ready" if ready else "not_ready",
            "services": {"s3": _s3_available, "supabase": _supabase_available},
        },
    )
