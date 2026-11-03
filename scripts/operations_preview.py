"""Explicit LOCAL synthetic UI QA server using SQLite. Not the PostgreSQL/Redis deployment."""

import os
import sys
import threading
import time
import uuid
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps/api"))

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from kubesentinel_api.config import get_settings  # noqa: E402
from kubesentinel_api.database import Base, get_db, get_redis  # noqa: E402
from kubesentinel_api.models import Incident  # noqa: E402, F401
from kubesentinel_api.operations import router as ops  # noqa: E402
from kubesentinel_api.operations.demo import fixture  # noqa: E402
from kubesentinel_api.operations.schemas import SnapshotBatch  # noqa: E402
from redis import Redis  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402


class PreviewRateLimiter:
    """Test-only in-process limiter. Production uses the actual Redis Lua implementation."""

    def __init__(self) -> None:
        self.values: dict[str, int] = {}
        self.lock = threading.Lock()

    def eval(self, script: str, count: int, key: str) -> int:
        key = f"{int(time.time()) // 60}:{key}"
        with self.lock:
            self.values[key] = self.values.get(key, 0) + 1
            return self.values[key]


def create_preview() -> FastAPI:
    settings = get_settings()
    if settings.app_env != "local" or settings.ops_auth_mode != "development":
        raise RuntimeError("Preview requires explicit local development authentication")
    settings.ops_demo_enabled = True
    directory = ROOT / ".cache/operations"
    directory.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        "sqlite:///" + (directory / "preview.sqlite").as_posix(),
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)

    def database() -> Any:
        with factory() as db:
            yield db

    limiter = cast(Redis, PreviewRateLimiter())
    ops.SessionLocal = factory
    app = FastAPI(title="Explicit synthetic UI QA preview; SQLite, not production storage")
    app.dependency_overrides[get_db] = database
    app.dependency_overrides[get_redis] = lambda: limiter

    @app.middleware("http")
    async def correlation(request: Request, call_next: Any) -> Any:
        request.state.correlation_id = str(uuid.uuid4())
        return await call_next(request)

    app.include_router(ops.router)
    with Session(engine) as db:
        ops.ingest(SnapshotBatch.model_validate(fixture()), db)
    return app


if __name__ == "__main__":
    uvicorn.run(
        create_preview(), host="127.0.0.1", port=int(os.environ.get("OPS_PREVIEW_PORT", "8000"))
    )
