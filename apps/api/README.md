# API and worker

FastAPI/Pydantic settings and schemas, SQLAlchemy 2.x, Alembic, psycopg, and Redis. `/api/v1/health` is process liveness; `/api/v1/ready` checks store connectivity and migration revision; `/api/v1/version` identifies the API. `/health` is a compatibility alias. Demo greeting jobs exercise durable SQL state, Redis completed-result caching and wake-up hints, and an independent worker.

No authentication, cluster credentials, or remediation actions are present. Use only trusted local environments. API requests log JSON with correlation IDs and sanitized errors. OpenAPI is available at `/openapi.json` and `/docs`. Run migrations before API/worker startup. See the [development guide](../../docs/development-guide.md) for all commands and failure behavior.
