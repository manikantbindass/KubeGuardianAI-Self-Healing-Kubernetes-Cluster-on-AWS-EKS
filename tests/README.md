# Tests

Phase 01 backend unit tests use isolated SQLite and mocked Redis; these are contract/behavior tests, not PostgreSQL locking evidence. The integration migration test requires an explicitly disposable PostgreSQL database ending `_test`; it skips visibly without configuration. Frontend component/client tests live beside source. `scripts/setup/smoke.py` exercises actual services and a greeting worker over HTTP. CI provisions an ephemeral PostgreSQL test service and a separate Compose stack.

Future end-to-end incident, security, load and chaos suites must have isolated targets, reproducible seeds and declared acceptance thresholds. No production fault injection is authorized. See [development commands](../docs/development-guide.md).
