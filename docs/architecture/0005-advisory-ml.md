# ADR 0005: advisory models and portable artifacts

- Status: accepted for local Phase 05 experiments
- Date: 2026-11-03

## Decision

Use fixed rules as the default, with robust MAD statistics and Isolation Forest as explicitly selected comparisons. Fit training-only transforms, tune validation-only thresholds, and retain purged time/incident splits for held-out evaluation. Keep real and synthetic provenance separate. Export bounded, checksummed JSON tree arrays instead of executable pickle/joblib artifacts. Publish incidents only through an authenticated, opt-in, real-only interface; expose no action-execution capability.

## Reason and consequences

The synthetic fixture favors rules. A functioning ML implementation is not evidence of better detection. Baselines remain usable during model corruption/loading failure. JSON traversal adds maintenance responsibility, covered by scikit-learn parity and topology/checksum tests, but keeps the serving image free of sklearn and unsafe deserialization. Checksums are not signatures; artifact access and approval are still required. Scores are uncalibrated; robust feature deviations are context, not causal attribution.

Defer LSTMs/autoencoders, public multi-tenant inference, automatic retraining/promotion and remediation until data, empirical evaluation and security boundaries justify them. See [architecture](anomaly-detection.md) and [model card](../../ml/models/model-card.md).
