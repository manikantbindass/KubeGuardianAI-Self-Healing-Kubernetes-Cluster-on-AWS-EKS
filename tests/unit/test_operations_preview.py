"""The explicitly synthetic launcher serves every dashboard intelligence route."""

from pathlib import Path

import operations_preview
import pytest
from fastapi.testclient import TestClient
from kubesentinel_api.config import get_settings
from kubesentinel_api.operations import router


def test_preview_intelligence_is_authenticated_and_mode_isolated(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("OPS_AUTH_MODE", "development")
    monkeypatch.setenv("OPS_DEV_TOKEN", "preview-test-token")
    monkeypatch.setattr(operations_preview, "ROOT", tmp_path)
    monkeypatch.setattr(router, "SessionLocal", router.SessionLocal)
    get_settings.cache_clear()
    try:
        with TestClient(operations_preview.create_preview()) as client:
            endpoint = "/api/v1/ops/intelligence"
            assert client.get(endpoint).status_code == 401
            headers = {"Authorization": "Bearer preview-test-token"}
            demo = client.get(endpoint + "?mode=demo", headers=headers)
            assert demo.status_code == 200, demo.text
            assert demo.json()["explanations"]
            real = client.get(endpoint + "?mode=real", headers=headers)
            assert real.status_code == 200, real.text
            assert real.json()["explanations"] == []
    finally:
        get_settings.cache_clear()
