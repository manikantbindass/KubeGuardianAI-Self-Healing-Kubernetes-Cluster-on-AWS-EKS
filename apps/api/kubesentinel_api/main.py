import logging
import re
import time
import uuid
from collections.abc import Awaitable, Callable
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from opentelemetry import propagate, trace
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from redis import Redis
from redis.exceptions import RedisError
from sqlalchemy import func, select, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session
from starlette.exceptions import HTTPException as StarletteHTTPException

from kubesentinel_api import __version__
from kubesentinel_api.config import get_settings
from kubesentinel_api.database import get_db, get_redis
from kubesentinel_api.instrumentation import (
    INCIDENTS,
    LATENCY,
    REQUESTS,
    STORE_UP,
    configure_tracing,
)
from kubesentinel_api.models import GreetingJob, Incident
from kubesentinel_api.observability import configure_logging
from kubesentinel_api.schemas import GreetingInput, GreetingOutput, Health, Readiness
from kubesentinel_api.telemetry import router as telemetry_router

settings = get_settings()
configure_logging(settings.log_level)
configure_tracing(settings.otel_exporter_otlp_endpoint)
logger = logging.getLogger("kubesentinel.api")
app = FastAPI(title="KubeSentinel AI", version=__version__, docs_url="/docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "X-Correlation-ID"],
    expose_headers=["X-Correlation-ID"],
    allow_credentials=False,
)


def error_response(request: Request, status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        {
            "error": {"code": code, "message": message},
            "correlation_id": request.state.correlation_id,
        },
        status_code=status,
        headers={"X-Correlation-ID": request.state.correlation_id},
    )


@app.middleware("http")
async def correlation(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    incoming = request.headers.get("X-Correlation-ID", "")
    request.state.correlation_id = (
        incoming if re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", incoming) else str(uuid.uuid4())
    )
    started = time.perf_counter()
    with trace.get_tracer("kubesentinel.api").start_as_current_span(
        "http.request", context=propagate.extract(dict(request.headers))
    ) as span:
        try:
            response = await call_next(request)
        except Exception:
            logger.error(
                "unhandled_request_error", extra={"correlation_id": request.state.correlation_id}
            )
            response = error_response(
                request, 500, "internal_error", "An unexpected error occurred."
            )
        route = getattr(request.scope.get("route"), "path", "unmatched")
        span.update_name(f"{request.method} {route}")
        span.set_attribute("http.response.status_code", response.status_code)
        logger.info(
            "http_request",
            extra={
                "correlation_id": request.state.correlation_id,
                "method": request.method,
                "path": route,
                "status": response.status_code,
            },
        )
    if route not in {"/metrics", "/health", "/api/v1/health", "/api/v1/ready"}:
        method = (
            request.method
            if request.method in {"GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS", "HEAD"}
            else "OTHER"
        )
        REQUESTS.labels(method, route, str(response.status_code)).inc()
        LATENCY.labels(method, route).observe(time.perf_counter() - started)
    response.headers["X-Correlation-ID"] = request.state.correlation_id
    response.headers["Cache-Control"] = "no-store"
    return response


@app.exception_handler(StarletteHTTPException)
async def http_error(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    return error_response(request, exc.status_code, "request_error", str(exc.detail))


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(request, 422, "validation_error", "Request validation failed.")


@app.exception_handler(SQLAlchemyError)
async def database_error(request: Request, exc: SQLAlchemyError) -> JSONResponse:
    logger.error("database_unavailable", extra={"correlation_id": request.state.correlation_id})
    return error_response(request, 503, "database_unavailable", "Database is unavailable.")


Db = Annotated[Session, Depends(get_db)]
Cache = Annotated[Redis, Depends(get_redis)]
router = APIRouter(prefix="/api/v1")


@router.get("/health", response_model=Health, tags=["system"])
@app.get("/health", response_model=Health, include_in_schema=False)
def health() -> Health:
    """Process liveness; deliberately independent of stores."""
    return Health()


@router.get("/version", tags=["system"])
def version() -> dict[str, str]:
    return {"version": __version__, "api_version": "v1", "environment": settings.app_env}


@router.get(
    "/ready", response_model=Readiness, responses={503: {"model": Readiness}}, tags=["system"]
)
def ready(db: Db, cache: Cache, response: Response) -> Readiness:
    dependencies: dict[str, Literal["ok", "unavailable"]] = {}
    try:
        db.execute(text("SELECT 1 FROM greeting_jobs LIMIT 1"))
        revision = db.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        dependencies["postgresql"] = "ok" if revision == "0002_incidents" else "unavailable"
    except SQLAlchemyError:
        dependencies["postgresql"] = "unavailable"
    try:
        dependencies["redis"] = "ok" if cache.ping() else "unavailable"
    except RedisError:
        dependencies["redis"] = "unavailable"
    available = all(value == "ok" for value in dependencies.values())
    response.status_code = 200 if available else 503
    return Readiness(status="ready" if available else "unavailable", dependencies=dependencies)


@router.get("/jobs", response_model=list[GreetingOutput], tags=["demo"])
def list_jobs(db: Db) -> list[GreetingJob]:
    return list(db.scalars(select(GreetingJob).order_by(GreetingJob.created_at.desc()).limit(20)))


@router.post("/jobs", response_model=GreetingOutput, status_code=202, tags=["demo"])
def create_job(payload: GreetingInput, db: Db, cache: Cache) -> GreetingJob:
    job = GreetingJob(name=payload.name.strip())
    db.add(job)
    db.commit()
    db.refresh(job)
    try:
        # SQL is durable work state. Redis is only a bounded wake-up hint.
        cache.lpush("sentinel:jobs", job.id)
        cache.ltrim("sentinel:jobs", 0, 999)
    except RedisError:
        logger.warning("queue_hint_unavailable")
    return job


@router.get("/jobs/{job_id}", response_model=GreetingOutput, tags=["demo"])
def get_job(job_id: uuid.UUID, db: Db, cache: Cache) -> GreetingOutput:
    key = f"sentinel:job:{job_id}"
    try:
        cached = cache.get(key)
        if isinstance(cached, str):
            return GreetingOutput.model_validate_json(cached)
    except (RedisError, ValueError):
        logger.warning("cache_read_unavailable")
    job = db.get(GreetingJob, str(job_id))
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found.")
    output = GreetingOutput.model_validate(job)
    # Only completed jobs are cached; queued state must remain live.
    if output.status == "completed":
        try:
            cache.setex(key, 30, output.model_dump_json())
        except RedisError:
            logger.warning("cache_write_unavailable")
    return output


app.include_router(router)
app.include_router(telemetry_router)


@app.get("/metrics", include_in_schema=False)
def prometheus_metrics(db: Db) -> Response:
    try:
        rows = db.execute(
            select(Incident.source, Incident.severity, Incident.status, func.count()).group_by(
                Incident.source, Incident.severity, Incident.status
            )
        )
        INCIDENTS.clear()
        for source, severity, status, count in rows:
            INCIDENTS.labels(source, severity, status).set(count)
        STORE_UP.set(1)
    except SQLAlchemyError:
        STORE_UP.set(0)
    return Response(generate_latest(), headers={"Content-Type": CONTENT_TYPE_LATEST})
