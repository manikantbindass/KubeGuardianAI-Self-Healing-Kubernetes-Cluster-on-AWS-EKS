# Domain services

The [anomaly detector](anomaly-detector/README.md) is an optional advisory service. Telemetry normalization lives in the API/event collector. Incident correlation, recovery policy, notifications, audit and assistant components remain planned. Phase 01's greeting worker is under `apps/api` and is unrelated to remediation.

Extract a separate process only for measured load, independent ownership, or isolation requirements. Interfaces and failure behavior are specified in the [system overview](../docs/architecture/system-overview.md).
