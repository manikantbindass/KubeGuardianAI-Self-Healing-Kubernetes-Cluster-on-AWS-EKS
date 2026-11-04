# Reproducible anomaly detection

`kubesentinel_ml` contains contracts, read-only collection, causal features, rules, JSON model inference, training and evaluation. `models/` holds the model card and reviewed metadata. Trained forests and raw JSONL stay in ignored `.cache/ml` or an access-controlled external artifact store.

Use the [cross-platform guide](../docs/runbooks/anomaly-detection.md). Exported real telemetry is unlabeled until an operator supplies reviewed incident labels/lineage; threshold tuning requires both validation classes. Unknown labels are not healthy ground truth. Never relabel synthetic data as real.

No LSTM/autoencoder is included: this fixture and the lack of independent real labels do not justify them. The [model card](models/model-card.md) documents limitations and promotion requirements.
