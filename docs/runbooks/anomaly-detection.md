# Run and evaluate anomaly detection

Use Python 3.12 and uv 0.13.6 from the repository root. Exact training/plotting versions and transitive dependencies are in `pyproject.toml`/`uv.lock`. Training extras are optional; ordinary application images exclude them. No AWS or Kubernetes writes are involved in these commands.

## Reproduce the synthetic benchmark

The following commands work in Windows PowerShell and Linux/macOS shells. Use `uv` on PATH; no Make or shell-specific environment syntax is required.

```sh
uv sync --frozen --extra ml
uv run --extra ml python scripts/ml.py generate
uv run --extra ml python scripts/ml.py train
uv run --extra ml python scripts/ml.py evaluate --output .cache/ml/repeated
uv run --extra ml pytest -m "not postgres"
```

Generation creates 1800 observations across 900 minutes from seed 42, all marked synthetic. Training writes `.cache/ml/model.json`, `evaluation/model-metadata.json`, `evaluation.json`, predictions CSV, three precision-recall CSVs and three measured plots. Raw data and forests stay out of Git. Small reviewed reference outputs live in [the report directory](../reports/phase-05). Repeated predictions/quality metrics are deterministic on the locked toolchain; latency and hardware/platform fields vary. Cross-platform model hashes may differ because metadata records Python/tool versions; prediction equivalence is tested separately.

Optional flags: `--seed 42 --trees 64 --max-samples 256 --window-seconds 60`. Use `--minutes 900` for the reference fixture and `--no-plots` for headless minimal runs. Time partitioning/purge and the validation FPR constraint are fixed safeguards. Retain failed evaluations rather than tuning against the final test set.

## Run the scoring service

```sh
uv run python scripts/serve_detector.py
```

Open [readiness](http://127.0.0.1:8010/ready), [metadata](http://127.0.0.1:8010/api/v1/model) or [OpenAPI](http://127.0.0.1:8010/docs). The native launcher reads `.cache/ml/model.json` by default. Missing/invalid artifacts activate rules with a visible readiness mode. In a second terminal:

```sh
uv run python scripts/test_detector_http.py
```

This performs 40 real HTTP requests at concurrency four, using explicitly synthetic payloads, checks explanations/health and saves measured HTTP latency. `--expected-mode rules_fallback` tests missing-model mode. The default API method is rules; this smoke test explicitly exercises Isolation Forest when loaded.

For Docker, generate/train first, then:

```sh
docker compose -f docker-compose.yml -f docker-compose.ml.yml config --quiet
docker compose -f docker-compose.yml -f docker-compose.ml.yml up --build --wait --wait-timeout 180
python scripts/test_detector_http.py
```

On Windows without `python` on PATH use `py -3.12`; on Linux/macOS use `python3`. The image is non-root, read-only, capability-free, with CPU/memory/PID limits and a read-only model mount. Model training is deliberately outside the runtime image. Start without a model by creating `.cache/ml` first; readiness will explicitly show fallback. Stop with the same Compose arguments followed by `down --remove-orphans`. Adding `--volumes` deletes local PostgreSQL/Redis data; do so only for disposable data.

## Collect actual telemetry

Start the [local monitoring stack](observability.md) and port-forward Prometheus 9090 and Loki 3100. Export an explicit past UTC range of one minute to six hours:

```sh
uv run python scripts/ml.py collect --data .cache/ml/real.jsonl --dataset-id local-lab-001 --start 2026-11-03T00:00:00+00:00 --end 2026-11-03T00:30:00+00:00 --kube-context kind-kubesentinel
```

Replace the example timestamps with a range present in your cluster. Omit `--kube-context` to exclude events explicitly. `--prometheus` and `--loki` select operator-trusted HTTP(S) endpoints. The sidecar records query definitions, missing source channels, collection time and data hash. No raw log/event messages are retained. Empty/missing sources are not manufactured into healthy measurements.

Real exports have null labels. Review incident lineage and ground-truth intervals separately; set `label`, `incident_id` and `fault_started_at` only from known evidence. Positive labels require incident IDs. Do not infer normality from absent incident records. Training real data requires both validation/test classes and enough baseline coverage; it may correctly refuse an insufficient export. Do not rename synthetic provenance to bypass that gate.

For near-real-time advisory rules on actual telemetry:

```sh
uv run python scripts/detect.py --kube-context kind-kubesentinel
uv run python scripts/detect.py --kube-context kind-kubesentinel --polls 0
```

The first command polls once; the second runs until Ctrl+C, without persisting raw data. Logs/metrics outages produce explicit unavailable status. Results retain missing-data quality and can fall back to rules.

## Optional incident publishing

Keep `DETECTOR_PUBLISH_ENABLED=false` during evaluation. To enable real-only delivery, configure random `DETECTOR_API_TOKEN`, backend `TELEMETRY_TOKEN` and matching `DETECTOR_TELEMETRY_TOKEN`; the Compose overlay maps the backend token to both services. Native clients read the detector token from process environment, so export it in the terminal running `detect.py`. Native service settings also read repository-root `.env`. Restart after changing settings.

Windows uses `$env:DETECTOR_API_TOKEN = 'your-local-random-token'`; Linux/macOS uses `export DETECTOR_API_TOKEN='your-local-random-token'`. Never commit actual tokens. Publishing requires `--publish` in the poller as well as server enablement. Synthetic data and synthetic-trained ML cannot publish. Fixed rules are the default; delivery failure returns `unavailable` while preserving scores. Retry the same interval to deduplicate. A later poll does not guarantee replay of every missed interval; archive/replay inputs externally when delivery durability matters.

The authenticated backend endpoint is `POST /api/v1/internal/anomalies`; evidence is readable at `GET /api/v1/incidents/{id}/anomaly`. Run `uv run alembic -c apps/api/alembic.ini upgrade head` before native API use. Compose runs migration 0003 automatically. Only use trusted local endpoints: production identity/tenant controls remain out of scope.

## Troubleshooting and rollback

- `rules_fallback`: inspect `/api/v1/model` model state, path/mount readability, checksum, feature version and configured window seconds. Use the trained artifact rather than the metadata-only JSON.
- Missing feature column or validation labels: collect more independent, reviewed data. Do not fill missing telemetry/labels with fabricated healthy zeros.
- 429: reduce client concurrency/batch size or polling frequency. Queue size is bounded by `DETECTOR_QUEUE_SIZE` (default 16); worker count stays two.
- 504: reduce batch/tree sizes or increase `DETECTOR_TIMEOUT_SECONDS` within its bounded range. Already-running work may finish after the deadline; retries use stable incident identities.
- 401/403/422 publishing: check separate credentials, explicit enablement, real provenance, completed intervals, score threshold and namespace. Synthetic-trained models are evaluation-only.
- Model rollback: stop detector, replace the mounted JSON with a previously approved artifact and restart; verify `/api/v1/model` hash. Remove the artifact to force rules. No automatic model update occurs.
- Incident migration rollback: stop all writers, back up PostgreSQL and downgrade to `0002_incidents` only with compatible old API code; this drops anomaly evidence. Normal model rollback does not require DB downgrade.

See the [model card](../../ml/models/model-card.md), [architecture](../architecture/anomaly-detection.md) and [validation](../reports/phase-05-validation.md) for empirical limits.
