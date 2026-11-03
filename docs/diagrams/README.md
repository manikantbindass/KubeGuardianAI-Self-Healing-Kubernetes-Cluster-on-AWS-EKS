# Architecture diagrams

The C4 and remediation diagrams show the **proposed target architecture**, not implemented cluster behavior. The local-services diagram shows the Phase 01 runtime definitions. Sources use standard Mermaid flowchart/sequence syntax with explicit C4 labels.

| Source | View |
| --- | --- |
| [c4-context.mmd](c4-context.mmd) | C4 level 1: people and external systems |
| [c4-container.mmd](c4-container.mmd) | C4 level 2: processes, stores, and trust boundaries |
| [c4-component.mmd](c4-component.mmd) | C4 level 3: backend components and independent operator |
| [remediation-sequence.mmd](remediation-sequence.mmd) | Proposal, approval, execution, audit, verification |
| [local-services.mmd](local-services.mmd) | Implemented local dashboard/API/worker and datastore dependencies |
| [anomaly-detection.mmd](anomaly-detection.mmd) | Phase 05 feature, training, evaluation and advisory scoring boundaries |

The [system overview](../architecture/system-overview.md) explains relationships, interfaces, failure behavior, environments, and alternatives. Run `npm run diagrams` to parse all `.mmd` sources. A successful parse checks grammar, not visual layout or architectural correctness; use a Mermaid-enabled editor to preview when changing layout.
