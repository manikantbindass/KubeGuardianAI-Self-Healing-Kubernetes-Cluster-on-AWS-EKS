# Secure recovery escalation webhooks

This optional extension delivers **real mirrored recovery actions** in phases
`Escalated`, `Failed` or `RolledBack` to one operator-configured receiver.
Notification delivery cannot approve, retry or execute Kubernetes remediation.
Other phases and synthetic/demo snapshots do not enqueue external notifications.

## Configure and start

Leave `ESCALATION_ENABLED=false` until you have a receiver that implements the
signature, freshness and idempotency contract below. Configuration is supplied
to both the API (enqueue) and worker (delivery); there is no browser/API setting
for a destination URL. URLs in incident data, policy escalation labels or model
recommendations are never used as network destinations.

Supply these values through your ignored `.env` for Compose, or a pre-created
Kubernetes Secret. Do not put real values in Git, Helm values or issue reports.

```dotenv
ESCALATION_ENABLED=true
ESCALATION_URL=https://your-approved-receiver.example/hooks/kubesentinel
ESCALATION_IP=YOUR_APPROVED_PUBLIC_NUMERIC_IP
ESCALATION_SIGNING_SECRET=YOUR_RANDOM_SECRET_AT_LEAST_32_BYTES
ESCALATION_MAX_ATTEMPTS=5
ESCALATION_MAX_PENDING=1000
```

The example host/IP/secret are placeholders, not a working service. The operator
must approve the receiver, pin its current public IP and arrange matching
credentials there. HTTPS on port 443 is required. TLS certificate verification
and SNI use the configured hostname; the socket connects to the pinned numeric
IP, preventing a subsequent DNS lookup from redirecting it to a private address.
Private, loopback and metadata IPs, URL user information, query strings,
fragments, redirects and environment proxies are not supported in deployment.
If the receiver changes IP, explicitly review and update the pin.

From the repository root, after the existing
[operations setup](operations-dashboard.md):

```sh
docker compose -f docker-compose.yml -f docker-compose.operations.yml up --build --wait --wait-timeout 180
```

The migrator upgrades to `0006_escalations` before API/worker startup. The usual
operations bridge must collect actual actions from the independently authorized
operator. This extension does not install or enable that operator automatically.

For Helm, set `escalation.enabled=true`, `escalation.secretName` to a pre-created
Secret containing the URL/IP/signing-secret keys, and enable/configure the
operations bridge as documented. API and worker import this Secret; dashboard
does not. Add only the approved destination IPv4 address as a `/32` on
TCP 443 to `networkPolicy.extraEgress`. IPv4 pins are currently required;
IPv6/translation/tunnel addresses are rejected. Default chart egress stays restricted.
Receiver adapters are required for systems with different payload/auth formats;
this is a generic signed JSON webhook, not a native Slack/PagerDuty connector.

## Payload and receiver verification

Example shape; values below are illustrative identifiers, not measured incidents:

```json
{
  "schema_version": 1,
  "event_id": "stable-64-character-digest",
  "type": "recovery.escalation",
  "action_uid": "kubernetes-action-uid",
  "namespace": "sentinel-lab",
  "action_name": "recovery-example",
  "phase": "Escalated",
  "recorded_at": "2026-11-05T00:00:00+00:00"
}
```

Only identifiers and a typed phase are exported: no raw logs, summaries,
approval keys, policy bodies, tokens or model prompts. Headers include:

- `X-KubeSentinel-Event-ID`: stable event identifier.
- `X-KubeSentinel-Timestamp`: UNIX seconds for this attempt.
- `X-KubeSentinel-Signature`: `sha256=` plus the hexadecimal HMAC-SHA256 over
  `timestamp + "." + exact_raw_request_body`, keyed with the shared secret.

The receiver must verify the signature with a constant-time comparison before
parsing/accepting the event, reject timestamps outside its bounded freshness
window (for example five minutes), compare header/body event IDs and atomically
deduplicate the event ID before side effects. Return 2xx only after durable
acceptance. Do not reserialize JSON before signature verification. Rotate the
shared secret through a coordinated receiver/API/worker change.

## Durable delivery behavior

The API writes the event and its enqueue audit in the snapshot transaction.
An event is deduplicated by destination fingerprint, namespace, action UID and
terminal phase, regardless of repeated snapshot resource versions. Different
terminal phases are distinct evidence. Enabling delivery can enqueue an already
terminal action when it next appears in a fresh collection.

PostgreSQL admission locks bound pending/sending events; duplicate inserts use
the unique event identity. If the backlog is full, collection returns 503 and
rolls back so the bridge must retry. This deliberately applies backpressure;
monitor the delivery backlog before enabling it on a busy cluster.

Workers claim rows with `FOR UPDATE SKIP LOCKED`, persist the attempt before I/O
and use a 30-second lease. An expired lease is retryable within the attempt
budget, so process crashes do not reset attempts. A reclaimed attempt cannot
have its outcome overwritten by an older worker. Socket operations have a
three-second default timeout (configurable 0.1–5 seconds).

2xx marks `delivered`. Network errors, 429 and 5xx retry with bounded exponential
backoff; other statuses (including redirects) mark `dead`. Attempts are bounded
(default five, configurable one to eight). Events older than 24 hours, removed
from namespace scope or configured for an old destination become `cancelled`.
Changing the configured destination does not silently forward its old backlog.
Disabled delivery leaves records untouched until re-enabled, when age/scope
checks apply. Dead/cancelled rows are not automatically replayed.

Delivery is **at least once**, not exactly once: a receiver can accept an event
before a worker crashes or its acknowledgement is lost. Receiver deduplication
is mandatory, including after the lease expires. No HTTP call is made inside
the snapshot ingestion transaction; worker retries cannot replay remediation.
Retain terminal rows/audit under an explicit operator data-retention policy;
automatic pruning and a replay UI are not part of this extension.

## Inspect and troubleshoot

Use existing operations Bearer authentication to call
`GET /api/v1/ops/escalations`. It returns the latest 100 deliveries in allowed
namespaces: state, attempts, timestamps and last HTTP status. It returns neither
the destination URL nor the signing key. The existing audit view also shows
`escalation.delivery` enqueue, attempt and outcome events.

If no events appear, check enabled settings on **both API and worker**, allowed
namespace, real collection mode and eligible terminal phase. For `pending` or
`sending`, inspect worker/database availability, lease/backoff and egress. For
`dead`, check receiver status, certificate, public IP pin and shared secret.
Response bodies and exception text are deliberately excluded from delivery
audit. Maintain time synchronization for receiver freshness checks.

## Verification

```sh
uv run pytest tests/unit/test_escalations.py -q
uv run pytest -m postgres
```

The first command includes a real disposable loopback HTTP receiver and tests
signature bytes, retries, crash leases, duplicates, demo isolation, API scope,
backpressure rollback, redaction and SSRF denial. It uses a test-only HTTP
exception restricted to `127.0.0.1` with `APP_ENV=local` and
`ESCALATION_LOCAL_HTTP=true`; this exception is not forwarded by Compose/Helm.
The PostgreSQL suite requires an explicit disposable `TEST_DATABASE_URL` ending
in `_test`. It verifies migrations and concurrent enqueue/worker claims against
real PostgreSQL; SQLite tests alone do not prove row-lock behavior.

Destination restriction follows the allowlist/pinned-address approach described
in the [OWASP SSRF prevention guidance](https://cheatsheetseries.owasp.org/cheatsheets/Server_Side_Request_Forgery_Prevention_Cheat_Sheet.html).
