FROM python:3.12.16-slim-trixie@sha256:b18b261e1b4974b4f321451ad5251ded85abb22c2b8b262da527dda1d031ab30
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN groupadd --gid 10001 sentinel && useradd --uid 10001 --gid sentinel --no-create-home sentinel
COPY --chown=10001:10001 apps/demo-workload/server.py /app/server.py
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=5s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=2)"]
CMD ["python", "/app/server.py"]
