"""
JusAds Compliance API
======================
Entry point. Initializes clients and mounts all route modules.

Usage:
  uvicorn app:app --reload --port 8000
"""

import logging
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent / ".env", override=True)

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent.supabase_client import SupabaseComplianceStore
from agent.s3_client import S3MediaClient

# ── Routes ────────────────────────────────────────────────────────────────────
from routes.compliance import router as compliance_router, init_compliance
from routes.remix import router as remix_router, init_remix
from routes.projects import router as projects_router, init_store as init_projects_store
from routes.health import router as health_router, init_health
from routes.progress import router as progress_router
from routes.generation import router as generation_router, init_generation

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── App ───────────────────────────────────────────────────────────────────────
app = FastAPI(title="JusAds Compliance API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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


# ── Initialize clients ────────────────────────────────────────────────────────
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

# ── Wire routes ───────────────────────────────────────────────────────────────
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
app.include_router(progress_router)

# ── Static files (dev only) ──────────────────────────────────────────────────
import os
IS_LAMBDA = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"

if not IS_LAMBDA and FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="frontend")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
