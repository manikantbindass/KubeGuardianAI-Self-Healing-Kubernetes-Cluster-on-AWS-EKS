FROM python:3.15.0-alpine3.24@sha256:2699b90f4d562a22e2dd076c82f964032f64814204bff36d271a54ba4cc2c7e2 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.15.0-alpine3.24@sha256:2699b90f4d562a22e2dd076c82f964032f64814204bff36d271a54ba4cc2c7e2 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" PYTHONPATH=/app
WORKDIR /app
RUN addgroup -g 10001 sentinel && adduser -D -H -u 10001 -G sentinel sentinel
COPY --from=builder --chown=sentinel:sentinel /app/.venv /app/.venv
COPY --chown=sentinel:sentinel apps/api/kubesentinel_api ./kubesentinel_api
COPY --chown=sentinel:sentinel apps/api/migrations ./migrations
COPY --chown=sentinel:sentinel apps/api/alembic.ini ./alembic.ini
USER 10001:10001
EXPOSE 8000
HEALTHCHECK --interval=10s --timeout=8s --start-period=10s --retries=12 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/v1/ready', timeout=7)"]
CMD ["uvicorn", "kubesentinel_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-access-log"]
