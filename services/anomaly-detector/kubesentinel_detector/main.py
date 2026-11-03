"""Bounded batch inference with deterministic fallback and opt-in incident delivery."""

import asyncio
import contextlib
import hmac
import json
import logging
import os
import urllib.error
import urllib.request
from collections.abc import AsyncIterator
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from kubesentinel_ml.features import windows
from kubesentinel_ml.model import Bundle
from kubesentinel_ml.rules import Score, rule_score
from kubesentinel_ml.schema import Observation
from pydantic import BaseModel, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger("kubesentinel.detector")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DETECTOR_", env_file=".env", extra="ignore")
    model_path: str = ""
    window_seconds: int = Field(default=60, ge=10, le=3600)
    queue_size: int = Field(default=16, ge=1, le=128)
    timeout_seconds: float = Field(default=10, gt=0, le=60)
    incident_api: str = "http://api:8000"
    telemetry_token: SecretStr = SecretStr("")
    publish_enabled: bool = False
    api_token: SecretStr = SecretStr("")

    @model_validator(mode="after")
    def publishing_credentials(self) -> "Settings":
        if self.publish_enabled and (
            not self.api_token.get_secret_value() or not self.telemetry_token.get_secret_value()
        ):
            raise ValueError("Publishing requires detector API token and backend telemetry token")
        return self


class ScoreRequest(BaseModel):
    observations: list[Observation] = Field(min_length=1, max_length=2000)
    detector: Literal["rules", "robust_statistics", "isolation_forest"] = "rules"
    publish: bool = False
    score_from: datetime | None = None

    @field_validator("score_from")
    @classmethod
    def aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("score_from requires a timezone")
        return value


class ScoredWindow(BaseModel):
    namespace: str
    resource: str
    start: datetime
    end: datetime
    provenance: str
    score: Score


class ScoreResponse(BaseModel):
    windows: list[ScoredWindow]
    mode: str
    delivery: str = "disabled"


class BodyLimit:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        received = 0

        async def bounded_receive() -> Message:
            nonlocal received
            message = await receive()
            received += len(message.get("body", b""))
            if received > 1_048_576:
                raise HTTPException(413, "Request exceeds 1 MiB")
            return message

        await self.app(scope, bounded_receive, send)


def predict(payload: ScoreRequest, bundle: Bundle | None, seconds: int) -> ScoreResponse:
    feature_windows = windows(payload.observations, seconds, max_windows=256)
    if len(feature_windows) > 256:
        raise ValueError("At most 256 windows per inference request")
    now = datetime.now(UTC)
    if any(row.timestamp > now for row in payload.observations):
        raise ValueError("Future telemetry is not accepted")
    results = []
    for window in feature_windows:
        if payload.score_from and window.start < payload.score_from:
            continue
        if window.end > now:
            continue  # A still-open window must not be published as a complete interval.
        score = (
            bundle.score(window, payload.detector)
            if bundle and payload.detector != "rules"
            else rule_score(window)
        )
        results.append(
            ScoredWindow(
                namespace=window.namespace,
                resource=window.resource,
                start=window.start,
                end=window.end,
                provenance=window.provenance,
                score=score,
            )
        )
    return ScoreResponse(windows=results, mode="trained" if bundle else "rules_fallback")


def deliver(result: ScoreResponse, settings: Settings) -> str:
    anomalies = [row for row in result.windows if row.score.anomalous]
    if not anomalies:
        return "no_anomalies"
    body = {
        "anomalies": [
            {
                "namespace": row.namespace,
                "resource": row.resource,
                "window_start": row.start.isoformat(),
                "window_end": row.end.isoformat(),
                "provenance": row.provenance,
                "detector": row.score.detector,
                "model_version": row.score.model_version or "rules-v1",
                "score": row.score.score,
                "threshold": row.score.threshold,
                "severity": row.score.severity,
                "explanations": [e.model_dump() for e in row.score.explanations],
            }
            for row in anomalies
        ]
    }
    request = urllib.request.Request(
        settings.incident_api.rstrip("/") + "/api/v1/internal/anomalies",
        data=json.dumps(body).encode(),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.telemetry_token.get_secret_value()}",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=3) as response:
            return "accepted" if response.status == 200 else "unavailable"
    except (OSError, ValueError, urllib.error.URLError):
        return "unavailable"  # Scoring remains successful; caller must retry same window identity.


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()
    bundle: Bundle | None = None
    model_state = "not_configured"
    if config.model_path:
        try:
            bundle = Bundle.load(Path(config.model_path))
            if bundle.window_seconds != config.window_seconds:
                raise ValueError("Configured window size differs from model")
            model_state = "loaded"
        except (OSError, ValueError):
            bundle = None
            model_state = "invalid_artifact"
    queue: asyncio.Queue[tuple[ScoreRequest, asyncio.Future[ScoreResponse]]] = asyncio.Queue(
        maxsize=config.queue_size
    )
    pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="detector")
    completed, shifted = 0, 0

    async def worker() -> None:
        nonlocal completed, shifted
        while True:
            payload, future = await queue.get()
            try:
                if future.cancelled():
                    continue
                loop = asyncio.get_running_loop()
                result = await loop.run_in_executor(
                    pool, predict, payload, bundle, config.window_seconds
                )
                if payload.publish:
                    result.delivery = await loop.run_in_executor(pool, deliver, result, config)
                completed += len(result.windows)
                shifted += sum(bool(w.score.drift) for w in result.windows)
                if not future.done():
                    future.set_result(result)
            except Exception as error:
                if not future.done():
                    future.set_exception(error)
            finally:
                queue.task_done()

    @asynccontextmanager
    async def lifespan(_: FastAPI) -> AsyncIterator[None]:
        workers = [asyncio.create_task(worker()) for _ in range(2)]
        yield
        for task in workers:
            task.cancel()
        for task in workers:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        pool.shutdown(wait=True, cancel_futures=True)

    app = FastAPI(
        title="KubeSentinel advisory anomaly detector", version="0.5.0", lifespan=lifespan
    )
    app.add_middleware(BodyLimit)

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        return {
            "status": "ready",
            "mode": "trained" if bundle else "rules_fallback",
            "model_state": model_state,
            "queue_depth": queue.qsize(),
        }

    @app.get("/api/v1/model")
    def metadata() -> dict[str, Any]:
        return {
            "model_state": model_state,
            "model_version": bundle.model_version if bundle else None,
            "metadata": bundle.metadata if bundle else {"baseline": "rules-v1"},
            "score_kind": "uncalibrated_anomaly_score",
            "remediation": "unsupported",
        }

    @app.get("/api/v1/drift")
    def drift() -> dict[str, Any]:
        return {
            "windows_scored": completed,
            "extreme_shift_windows": shifted,
            "shift_rate": shifted / completed if completed else None,
            "policy": "robust deviation >12; advisory, no automatic retraining",
            "persistence": "process-lifetime counters reset on restart",
        }

    @app.post("/api/v1/score", response_model=ScoreResponse)
    async def score(payload: ScoreRequest, request: Request) -> ScoreResponse:
        api_token = config.api_token.get_secret_value()
        if api_token and not hmac.compare_digest(
            request.headers.get("Authorization", "").encode(), f"Bearer {api_token}".encode()
        ):
            raise HTTPException(401, "Invalid detector credentials")
        if payload.publish:
            if not config.publish_enabled or not config.telemetry_token.get_secret_value():
                raise HTTPException(403, "Incident publishing is disabled")
            if any(row.provenance != "real" for row in payload.observations):
                raise HTTPException(422, "Synthetic telemetry cannot publish live incidents")
            if payload.detector != "rules" and bundle and bundle.metadata["provenance"] != "real":
                raise HTTPException(422, "Synthetic-trained models are evaluation-only; use rules")
        future: asyncio.Future[ScoreResponse] = asyncio.get_running_loop().create_future()
        try:
            queue.put_nowait((payload, future))
        except asyncio.QueueFull as error:
            raise HTTPException(
                429, "Inference queue is full", headers={"Retry-After": "1"}
            ) from error
        try:
            return await asyncio.wait_for(asyncio.shield(future), config.timeout_seconds)
        except TimeoutError as error:
            # Capacity stays occupied until already-started work actually ends.
            future.cancel()
            raise HTTPException(504, "Inference deadline exceeded") from error
        except ValueError as error:
            raise HTTPException(422, str(error)) from error

    @app.exception_handler(Exception)
    async def unexpected(request: Request, _: Exception) -> JSONResponse:
        logger.error(
            json.dumps({"event": "detector_error", "path": request.url.path, "pid": os.getpid()})
        )
        return JSONResponse({"detail": "Scoring failed; no action executed"}, status_code=500)

    return app


app = create_app()
