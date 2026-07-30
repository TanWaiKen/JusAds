"""Post-performance routes backed only by live Zernio analytics."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse

from shared.zernio_client import (
    ZernioServiceError,
    get_best_time_to_post,
    get_connected_accounts,
    get_daily_metrics,
    get_overall_analytics,
    get_posts_list,
)
from routes.profile import _get_stored_user_zernio_key
from shared.auth import Principal, get_current_principal
from shared.zernio_key_vault import ZernioKeySecurityError

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/statistics", tags=["statistics"])


async def _live_response(operation: Callable[[], Awaitable[dict[str, Any]]]) -> JSONResponse:
    """Map live Zernio results and failures to stable HTTP responses."""
    try:
        return JSONResponse(content=await operation())
    except ZernioServiceError as exc:
        logger.warning("[StatisticsAPI] Zernio unavailable: %s", exc)
        return JSONResponse(
            status_code=503 if exc.not_configured else 502,
            content={
                "error": (
                    "Connect a Zernio account in Profile before loading analytics."
                    if exc.not_configured
                    else "Social analytics are temporarily unavailable."
                ),
                "code": "zernio_not_configured" if exc.not_configured else "zernio_unavailable",
                "source": "unavailable",
            },
        )
    except Exception:
        logger.exception("[StatisticsAPI] Unexpected analytics failure")
        return JSONResponse(
            status_code=500,
            content={"error": "Unable to load social analytics.", "code": "analytics_error"},
        )


async def _live_for_principal(
    principal: Principal,
    operation: Callable[[str], Awaitable[dict[str, Any]]],
) -> JSONResponse:
    """Resolve only the caller's key and keep key-storage failures explicit."""
    try:
        api_key = _get_stored_user_zernio_key(principal.email)
    except ZernioKeySecurityError:
        return JSONResponse(
            status_code=503,
            content={"error": "Secure Zernio key storage is unavailable.", "code": "zernio_key_storage_unavailable"},
        )
    return await _live_response(lambda: operation(api_key))


@router.get("")
async def get_statistics_overview(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Get live overall analytics from Zernio."""
    return await _live_for_principal(principal, lambda api_key: get_overall_analytics(api_key=api_key))


@router.get("/daily")
async def get_daily_stats(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Get live daily aggregate metrics from Zernio."""
    return await _live_for_principal(principal, lambda api_key: get_daily_metrics(api_key=api_key))


@router.get("/best-times")
async def get_best_times(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """Get live recommended posting times from Zernio."""
    return await _live_for_principal(principal, lambda api_key: get_best_time_to_post(api_key=api_key))


@router.get("/accounts")
async def get_accounts(principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """List live connected Zernio accounts."""
    return await _live_for_principal(principal, lambda api_key: get_connected_accounts(api_key=api_key))


@router.get("/posts")
async def get_posts(platform: Optional[str] = None, principal: Principal = Depends(get_current_principal)) -> JSONResponse:
    """List live Zernio posts without synthetic fallback metrics."""
    return await _live_for_principal(principal, lambda api_key: get_posts_list(api_key=api_key, platform=platform))
