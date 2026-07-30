"""
JusAds Compliance API
======================
Entry point. Initializes clients and mounts all route modules.

Usage:
  uvicorn app:app --reload --port 8000
"""

import asyncio
import logging
import os
import sys
import uuid
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared.supabase_client import SupabaseComplianceStore
from shared.s3_client import S3MediaClient

# -- Routes --------------------------------------------------------------------
from routes.compliance import router as compliance_router, init_compliance
from routes.remix import router as remix_router, init_remix
from routes.projects import router as projects_router, init_store as init_projects_store
from routes.health import router as health_router, init_health
from routes.profile import router as profile_router
from routes.generation import router as generation_router, init_generation
from routes.files import router as files_router
from routes.trends import router as trends_router
from routes.statistics import router as statistics_router

logging.basicConfig(level=logging.INFO)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("filelock").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# -- Startup secret check (Req 3.5, 3.6) ---------------------------------------
# Halt before serving any request when a required secret is missing. The check
# logs the missing secret BY NAME ONLY and raises, preventing the app from
# starting rather than serving in a broken state.
from config import CORS_ORIGINS, ENVIRONMENT, verify_required_secrets

verify_required_secrets()

# -- App -----------------------------------------------------------------------
app = FastAPI(title="JusAds Compliance API")
_recheck_worker_task: asyncio.Task | None = None


async def _run_remediation_recheck_loop() -> None:
    """Keep the durable remediation outbox moving without blocking API requests.

    The database claim RPC uses row locks, so multiple API replicas can run this
    loop safely.  Each actual model evaluation executes in a worker thread.
    """
    from jusads_compliance.remediation_recheck_worker import WORKER_POLL_SECONDS, run_once

    while True:
        try:
            await asyncio.to_thread(run_once)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("[RemediationRecheck] Background worker iteration failed")
        await asyncio.sleep(WORKER_POLL_SECONDS)


@app.on_event("startup")
async def start_remediation_recheck_worker() -> None:
    global _recheck_worker_task
    if os.environ.get("REMEDIATION_RECHECK_WORKER_ENABLED", "true").strip().lower() in {"1", "true", "yes"}:
        _recheck_worker_task = asyncio.create_task(_run_remediation_recheck_loop())
        logger.info("[RemediationRecheck] Background worker enabled")


@app.on_event("shutdown")
async def stop_remediation_recheck_worker() -> None:
    global _recheck_worker_task
    if _recheck_worker_task:
        _recheck_worker_task.cancel()
        try:
            await _recheck_worker_task
        except asyncio.CancelledError:
            pass
        _recheck_worker_task = None


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Attach a stable correlation id without trusting arbitrary client values."""
    supplied = request.headers.get("X-Request-ID", "").strip()
    request_id = supplied if supplied and len(supplied) <= 128 else str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    return response

if ENVIRONMENT == "production" and not CORS_ORIGINS:
    logger.warning("[Init] No CORS origins configured; only same-origin requests are expected")

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(CORS_ORIGINS),
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.exception_handler(ValidationError)
async def pydantic_validation_exception_handler(request, exc: ValidationError) -> JSONResponse:
    errors = exc.errors()
    messages = [e.get("msg", "Validation error") for e in errors]
    return JSONResponse(status_code=400, content={"error": "; ".join(messages)})


@app.exception_handler(RequestValidationError)
async def request_validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    messages = [e.get("msg", "Validation error") for e in errors]
    return JSONResponse(status_code=400, content={"error": "; ".join(messages)})


# -- Initialize clients --------------------------------------------------------
try:
    s3_client = S3MediaClient()
    logger.info("[Init] S3MediaClient OK")
except Exception as e:
    logger.warning("[Init] S3MediaClient failed: %s", e)
    s3_client = None

try:
    supabase_store = SupabaseComplianceStore()
    logger.info("[Init] SupabaseComplianceStore OK")
except Exception as e:
    logger.warning("[Init] SupabaseComplianceStore failed: %s", e)
    supabase_store = None

# -- Wire routes ---------------------------------------------------------------
init_compliance(supabase_store, s3_client)
init_remix(supabase_store)
init_projects_store(supabase_store)
init_generation(supabase_store)
init_health(s3_ok=s3_client is not None, supabase_ok=supabase_store is not None)

app.include_router(compliance_router)
app.include_router(remix_router)
app.include_router(projects_router)
app.include_router(generation_router)
app.include_router(health_router)
app.include_router(profile_router)
app.include_router(files_router)
app.include_router(trends_router)
app.include_router(statistics_router)

# -- Static files (dev only) --------------------------------------------------
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if not IS_LAMBDA and FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
