FROM python:3.12.16-alpine3.24@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8 AS builder
COPY --from=ghcr.io/astral-sh/uv:0.13.6@sha256:af22a52f5eafef3d78e551599d405c02df61919d18028f0cea8eda93bc9986d0 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

FROM python:3.12.16-alpine3.24@sha256:e6dae589c1c05976188fd3bd019afd091445fc533ed2ea29001beddc7368a9c8 AS runtime
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PATH="/app/.venv/bin:$PATH" PYTHONPATH="/app/ml:/app/service"
WORKDIR /app
RUN addgroup -g 10001 sentinel && adduser -D -H -u 10001 -G sentinel sentinel
COPY --from=builder --chown=sentinel:sentinel /app/.venv /app/.venv
COPY --chown=sentinel:sentinel ml/kubesentinel_ml /app/ml/kubesentinel_ml
COPY --chown=sentinel:sentinel services/anomaly-detector/kubesentinel_detector /app/service/kubesentinel_detector
USER 10001:10001
EXPOSE 8010
HEALTHCHECK --interval=10s --timeout=3s --start-period=10s --retries=6 CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/ready', timeout=2)"]
CMD ["uvicorn", "kubesentinel_detector.main:app", "--host", "0.0.0.0", "--port", "8010", "--no-access-log"]
