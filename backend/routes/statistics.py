"""
routes/statistics.py
────────────────────
Post performance statistics API — directly calls Zernio production API.

No caching, no project filtering — just returns live data from the
connected Zernio account (all platforms, all posts).

Requirements: 12.1, 12.2, 12.3, 12.4, 12.5, 12.6
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from shared.zernio_client import (
    get_overall_analytics,
    get_daily_metrics,
    get_best_time_to_post,
    get_connected_accounts,
    get_posts_list,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/statistics", tags=["statistics"])


@router.get("")
@router.get("/")
async def get_statistics_overview() -> JSONResponse:
    """Get overall analytics — all posts, all platforms from Zernio.

    Returns overview metrics, per-post analytics, and platform breakdown.
    """
    try:
        data = await get_overall_analytics()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error("[StatisticsAPI] Failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/daily")
async def get_daily_stats() -> JSONResponse:
    """Get daily aggregated metrics from Zernio."""
    try:
        data = await get_daily_metrics()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error("[StatisticsAPI] daily metrics failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/best-times")
async def get_best_times() -> JSONResponse:
    """Get best times to post from Zernio."""
    try:
        data = await get_best_time_to_post()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error("[StatisticsAPI] best times failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/accounts")
async def get_accounts() -> JSONResponse:
    """List connected social accounts."""
    try:
        data = await get_connected_accounts()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error("[StatisticsAPI] accounts failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})


@router.get("/posts")
async def get_posts() -> JSONResponse:
    """List all posts from Zernio."""
    try:
        data = await get_posts_list()
        return JSONResponse(content=data)
    except Exception as e:
        logger.error("[StatisticsAPI] posts list failed: %s", e)
        return JSONResponse(status_code=500, content={"error": str(e)})
