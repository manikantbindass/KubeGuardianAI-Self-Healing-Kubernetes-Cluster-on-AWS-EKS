"""Namespaced core/v1 Event polling; PostgreSQL dedup survives collector restarts."""

import json
import logging
import os
import signal
import ssl
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from types import FrameType
from typing import Any

from kubesentinel_api.config import get_settings
from kubesentinel_api.observability import configure_logging


def normalize(event: dict[str, Any]) -> dict[str, Any]:
    metadata = event["metadata"]
    obj = event.get("involvedObject", {})
    return {
        "uid": metadata["uid"],
        "resource_version": metadata["resourceVersion"],
        "namespace": metadata["namespace"],
        "resource": str(obj.get("name", "unknown"))[:253],
        "reason": str(event.get("reason", "Unknown"))[:128],
        "message": str(event.get("message", ""))[:1024],
        "type": event.get("type", "Normal"),
        "count": event.get("series", {}).get("count", event.get("count", 1)),
        "observed_at": event.get("series", {}).get("lastObservedTime")
        or event.get("lastTimestamp")
        or event.get("eventTime")
        or metadata.get("creationTimestamp")
        or datetime.now(UTC).isoformat(),
    }


def main() -> None:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = logging.getLogger("kubesentinel.events")
    service_account = Path("/var/run/secrets/kubernetes.io/serviceaccount")
    context = ssl.create_default_context(cafile=str(service_account / "ca.crt"))
    host = os.environ["KUBERNETES_SERVICE_HOST"]
    port = os.environ.get("KUBERNETES_SERVICE_PORT", "443")
    api = f"https://{host}:{port}"
    destination = os.environ.get("INGESTION_URL", "http://sentinel-api:8000")
    running = True

    def stop(signum: int, frame: FrameType | None) -> None:
        nonlocal running
        running = False

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    while running:
        try:
            # Read projected token every poll to support Kubernetes token rotation.
            token = (service_account / "token").read_text().strip()
            request = urllib.request.Request(
                api + "/api/v1/namespaces/kubesentinel/events?limit=500",
                headers={"Authorization": f"Bearer {token}"},
            )
            with urllib.request.urlopen(request, context=context, timeout=5) as response:
                batch = json.load(response)
            for event in batch["items"]:
                if event.get("type") != "Warning":
                    continue
                payload = json.dumps(normalize(event)).encode()
                request = urllib.request.Request(
                    destination + "/api/v1/internal/events",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": "Bearer " + settings.telemetry_token.get_secret_value(),
                    },
                )
                with urllib.request.urlopen(request, timeout=5):
                    pass
            Path("/tmp/event-collector-heartbeat").touch()
            logger.info("event_poll_completed")
        except (OSError, ValueError, KeyError):
            logger.warning("event_poll_failed")
        time.sleep(10)


if __name__ == "__main__":
    main()
