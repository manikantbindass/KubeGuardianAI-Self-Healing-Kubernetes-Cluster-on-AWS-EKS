# Scripts

`setup/smoke.py` checks actual dashboard/API readiness and greeting completion, or backend-unavailable behavior. `validate_repository.py` checks essential docs, local file links and original license content. `validate-diagrams.mjs` parses editable Mermaid diagrams using locked Node tooling. Cloud provisioning remains manual and authorization-gated. `delivery.py` prepares GitOps changes or collects read-only staging evidence; `image_delivery.py publish` writes approved ECR artifacts only in the protected release workflow. Local kind/operator scripts execute scoped test actions; inspect their context guards before use.

Future deploy/cleanup/docs-generation automation must declare targets, outputs, scope and rollback; cleanup must avoid global deletion or unverified contexts.
