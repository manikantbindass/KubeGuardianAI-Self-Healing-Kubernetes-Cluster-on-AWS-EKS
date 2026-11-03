"""Low-cardinality HTTP metrics and optional OTLP trace export."""

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from prometheus_client import Counter, Gauge, Histogram

REQUESTS = Counter(
    "sentinel_http_requests_total", "Application HTTP requests", ["method", "route", "status"]
)
LATENCY = Histogram(
    "sentinel_http_duration_seconds",
    "Application request latency",
    ["method", "route"],
    buckets=(0.01, 0.05, 0.1, 0.3, 0.5, 1, 3, 10),
)
INCIDENTS = Gauge("sentinel_incidents", "Durable incidents", ["source", "severity", "status"])
STORE_UP = Gauge("sentinel_incident_store_up", "Incident metrics database query availability")
REMEDIATIONS = Counter(
    "sentinel_remediation_actions_total",
    "API-local counters; operator outcomes use CRD audit",
    ["outcome"],
)
for outcome in ("completed", "failed", "denied"):
    REMEDIATIONS.labels(outcome).inc(0)


def configure_tracing(endpoint: str) -> None:
    if endpoint:
        provider = TracerProvider(resource=Resource.create({"service.name": "sentinel-api"}))
        provider.add_span_processor(
            BatchSpanProcessor(
                OTLPSpanExporter(endpoint=endpoint.rstrip("/") + "/v1/traces", timeout=3)
            )
        )
        trace.set_tracer_provider(provider)
