# Future domain services

Telemetry, anomaly detection, incident correlation, recovery policy, and assistant boundaries have dedicated responsibility notes. Notification and audit components will initially share backend domain infrastructure and use a transactional outbox before any cluster action. They are target architecture, not running services. Phase 01's greeting worker is under `apps/api` and is unrelated to remediation.

Extract a separate process only for measured load, independent ownership, or isolation requirements. Interfaces and failure behavior are specified in the [system overview](../docs/architecture/system-overview.md).
