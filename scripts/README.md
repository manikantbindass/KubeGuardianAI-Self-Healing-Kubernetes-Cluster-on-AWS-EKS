# Scripts

`setup/smoke.py` checks actual dashboard/API readiness and greeting completion, or backend-unavailable behavior. `validate_repository.py` checks essential docs, local file links and original license content. `validate-diagrams.mjs` parses editable Mermaid diagrams using locked Node tooling. No script deploys cloud infrastructure or executes cluster actions.

Future deploy/cleanup/docs-generation automation must declare targets, outputs, scope and rollback; cleanup must avoid global deletion or unverified contexts.
