"""Post-performance routes backed only by live Zernio analytics."""

import logging
from collections.abc import Awaitable, Callable
from typing import Any, Optional

from fastapi import APIRouter, Query
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
                "error": str(exc),
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


@router.get("")
@router.get("/")
async def get_statistics_overview(email: str = Query(...)) -> JSONResponse:
    """Get live overall analytics from Zernio."""
    api_key = _get_stored_user_zernio_key(email)
    return await _live_response(lambda: get_overall_analytics(api_key=api_key))


@router.get("/daily")
async def get_daily_stats(email: str = Query(...)) -> JSONResponse:
    """Get live daily aggregate metrics from Zernio."""
    api_key = _get_stored_user_zernio_key(email)
    return await _live_response(lambda: get_daily_metrics(api_key=api_key))


@router.get("/best-times")
async def get_best_times(email: str = Query(...)) -> JSONResponse:
    """Get live recommended posting times from Zernio."""
    api_key = _get_stored_user_zernio_key(email)
    return await _live_response(lambda: get_best_time_to_post(api_key=api_key))


@router.get("/accounts")
async def get_accounts(email: str = Query(...)) -> JSONResponse:
    """List live connected Zernio accounts."""
    api_key = _get_stored_user_zernio_key(email)
    return await _live_response(lambda: get_connected_accounts(api_key=api_key))


@router.get("/posts")
async def get_posts(email: str = Query(...), platform: Optional[str] = None) -> JSONResponse:
    """List live Zernio posts without synthetic fallback metrics."""
    api_key = _get_stored_user_zernio_key(email)
    return await _live_response(lambda: get_posts_list(api_key=api_key, platform=platform))
