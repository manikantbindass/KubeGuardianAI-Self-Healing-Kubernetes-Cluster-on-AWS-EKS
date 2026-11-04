# Domain services

The [anomaly detector](anomaly-detector/README.md) is an optional advisory service. Telemetry normalization lives in the API/event collector. The [recovery policy pipeline](recovery-engine/README.md) is implemented inside the guarded Go operator, not as a separate service. Incident correlation, external notifications/audit export and assistant components remain planned. Phase 01's greeting worker is under `apps/api` and is unrelated to remediation.

Extract a separate process only for measured load, independent ownership, or isolation requirements. Interfaces and failure behavior are specified in the [system overview](../docs/architecture/system-overview.md).
