import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from kubesentinel_detector import main
from kubesentinel_detector.main import Settings, create_app
from kubesentinel_ml.dataset import synthetic
from pydantic import SecretStr


def payload() -> dict[str, object]:
    return {
        "observations": [r.model_dump(mode="json") for r in synthetic(minutes=300)[100:108]],
        "detector": "isolation_forest",
    }


def test_fallback_health_batch_and_synthetic_publish_protection(tmp_path: Path) -> None:
    invalid = tmp_path / "bad.json"
    invalid.write_text('{"corrupt":true}')
    settings = Settings(
        model_path=str(invalid),
        publish_enabled=True,
        api_token=SecretStr("detector-token"),
        telemetry_token=SecretStr("backend-token"),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/ready").json()["model_state"] == "invalid_artifact"
        assert client.get("/api/v1/model").json()["score_kind"] == "uncalibrated_anomaly_score"
        assert client.post("/api/v1/score", json=payload()).status_code == 401
        headers = {"Authorization": "Bearer detector-token"}
        scored = client.post("/api/v1/score", json=payload(), headers=headers)
        assert scored.status_code == 200
        assert scored.json()["mode"] == "rules_fallback"
        assert all(w["score"]["detector"] == "rules" for w in scored.json()["windows"])
        assert (
            client.post(
                "/api/v1/score", json={**payload(), "publish": True}, headers=headers
            ).status_code
            == 422
        )
        assert client.get("/api/v1/drift").json()["windows_scored"] == 4
        body = '{"observations":[],"padding":"' + "x" * 1_048_576 + '"}'
        assert client.post("/api/v1/score", content=body, headers=headers).status_code == 413


def test_bounded_queue_timeout_and_liveness(monkeypatch: pytest.MonkeyPatch) -> None:
    released = threading.Event()
    original = main.predict

    def blocked(*args: object) -> main.ScoreResponse:
        released.wait(2)
        return original(*args)  # type: ignore[arg-type]

    monkeypatch.setattr(main, "predict", blocked)
    with TestClient(create_app(Settings(queue_size=1, timeout_seconds=0.05))) as client:
        with ThreadPoolExecutor(max_workers=12) as pool:
            jobs = [pool.submit(client.post, "/api/v1/score", json=payload()) for _ in range(12)]
            codes = [job.result().status_code for job in jobs]
            assert 429 in codes and 504 in codes
            assert client.get("/health").status_code == 200
            released.set()
