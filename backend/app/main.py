from __future__ import annotations

import logging
import uuid
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.router import api_router
from app.config import get_settings
from app.database import get_db
from app.errors import install_error_handlers
from app.schemas import HealthOut


settings = get_settings()
logger = logging.getLogger("findit")


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings.media_root.mkdir(parents=True, exist_ok=True)
    yield


app = FastAPI(
    title="FindIt Next 2.0 — Campus Recovery Network API",
    version="2.0.0",
    description=(
        "Secure campus lost-and-found reporting, deterministic matching, ownership claims, "
        "staff custody, and verified handovers. Match scores are explainable heuristics, not probabilities."
    ),
    lifespan=lifespan,
    docs_url=None if settings.environment in {"production", "staging"} else "/docs",
    redoc_url=None if settings.environment in {"production", "staging"} else "/redoc",
    openapi_url=None if settings.environment in {"production", "staging"} else "/openapi.json",
)

app.add_middleware(GZipMiddleware, minimum_size=1000)
if settings.environment in {"production", "staging"}:
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request.state.request_id = (request.headers.get("X-Request-ID") or str(uuid.uuid4()))[:100]
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.environment in {"production", "staging"}:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


install_error_handlers(app)
app.include_router(api_router)


@app.get("/api/v1/health", response_model=HealthOut, tags=["system"])
def health(db: Session = Depends(get_db)) -> HealthOut:
    db.execute(select(1))
    return HealthOut(status="ok", database="ok", version=app.version)



@app.get("/api/v1/live", include_in_schema=False)
def liveness() -> dict[str, str]:
    """Liveness does not require a database; readiness is checked by /health."""
    return {"status": "ok"}
