"""Isolated fault fixture. Modes are controlled only by the lab test Deployment."""

import os
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

MODE = os.environ.get("MODE", "healthy")
START = time.monotonic()
if MODE == "crash":
    time.sleep(3)
    raise SystemExit(1)
if MODE == "oom":
    time.sleep(3)
    _memory = bytearray(128 * 1024 * 1024)


class Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if MODE == "latency":
            time.sleep(0.7)
        unhealthy = MODE == "not-ready" and self.path == "/ready"
        # Restart fixes only a transient per-process fault, not broken deployment configuration.
        unhealthy = unhealthy or (MODE == "transient" and time.monotonic() - START > 35)
        self.send_response(503 if unhealthy else 200)
        self.end_headers()
        self.wfile.write(b"unhealthy" if unhealthy else b"healthy")

    def log_message(self, format: str, *args: object) -> None:
        pass


ThreadingHTTPServer(("0.0.0.0", 8080), Handler).serve_forever()
