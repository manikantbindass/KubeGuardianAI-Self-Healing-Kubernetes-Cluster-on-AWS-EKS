"""Real PostgreSQL claim/deduplication test; only disposable *_test databases."""

import os
import subprocess
import sys
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from kubesentinel_api.config import get_settings
from kubesentinel_api.escalations import Escalation, enqueue_escalation, process_escalation
from kubesentinel_api.operations.models import OperationsAudit
from sqlalchemy import create_engine, delete, func, select
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session


@pytest.mark.postgres
def test_postgres_deduplication_and_worker_lease(monkeypatch: pytest.MonkeyPatch) -> None:
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL unset; PostgreSQL concurrency requires a disposable DB")
    assert (make_url(url).database or "").endswith("_test")
    for key, value in {
        "ESCALATION_ENABLED": "true",
        "ESCALATION_URL": "https://receiver.example/hook",
        "ESCALATION_IP": "8.8.8.8",
        "ESCALATION_SIGNING_SECRET": "x" * 40,
        "OPS_NAMESPACES": '["sentinel-lab"]',
    }.items():
        monkeypatch.setenv(key, value)
    get_settings.cache_clear()
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", "apps/api/alembic.ini", "upgrade", "head"],
        cwd=Path(__file__).resolve().parents[2],
        env={**os.environ, "DATABASE_URL": url},
        check=True,
        timeout=60,
    )
    engine = create_engine(url)
    uid = str(uuid.uuid4())
    started, release = threading.Event(), threading.Event()
    sent: list[str] = []

    def send(*args: object) -> int:
        sent.append(str(args[2]))
        started.set()
        assert release.wait(10)
        return 204

    def enqueue() -> None:
        with Session(engine) as db:
            enqueue_escalation(
                db, "real", "sentinel-lab", "recovery", uid, {"status": {"phase": "Escalated"}}
            )
            db.commit()

    def process() -> bool:
        with Session(engine) as db:
            return process_escalation(db)

    monkeypatch.setattr("kubesentinel_api.escalations.deliver", send)
    identity = ""
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            list(pool.map(lambda _: enqueue(), range(2)))
            with Session(engine) as db:
                assert db.scalar(select(func.count()).select_from(Escalation)) == 1
                row = db.scalar(select(Escalation))
                assert row
                identity = row.id
            first = pool.submit(process)
            assert started.wait(10)
            # The committed lease prevents a second replica claiming the same delivery.
            assert pool.submit(process).result(timeout=5) is False
            release.set()
            assert first.result(timeout=10)
        with Session(engine) as db:
            row = db.get(Escalation, identity)
            assert row and row.state == "delivered" and row.attempts == 1
        assert len(sent) == 1
    finally:
        release.set()
        if identity:
            with Session(engine) as db:
                db.execute(delete(OperationsAudit).where(OperationsAudit.target == identity))
                db.execute(delete(Escalation).where(Escalation.id == identity))
                db.commit()
        engine.dispose()
        get_settings.cache_clear()
