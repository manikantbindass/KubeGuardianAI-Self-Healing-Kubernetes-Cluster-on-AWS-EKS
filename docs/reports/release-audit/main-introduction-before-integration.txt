# KubeSentinel AI

An evolving platform for observing Kubernetes workloads and developing policy-driven, safely controlled recovery workflows. This repository retains its original name while the project adopts the KubeSentinel AI identity.

## Project status

The default branch currently contains the project introduction and the original Apache License 2.0. Application code and infrastructure are under development in separate pull requests:

| Workstream | Implementation and review |
| --- | --- |
| Full-stack foundation | [Phase 01: dashboard, API and local development](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/pull/1) |
| Local Kubernetes | [Phase 02: kind deployment and Helm charts](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/pull/2) |
| AWS infrastructure as code | [Phase 03: Terraform modules and operating guides](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/pull/3) |
| Observability | [Phase 04: telemetry and incident ingestion](https://github.com/manikantbindass/KubeGuardianAI-Self-Healing-Kubernetes-Cluster-on-AWS-EKS/pull/4) |

These pull requests have their own validation results and limitations. Follow their setup documentation when evaluating a development branch. This introduction does not claim that the default branch runs the application or that an AWS deployment exists.

## Direction

The intended platform combines a Next.js dashboard, FastAPI services, PostgreSQL and Redis, Kubernetes orchestration, observability, anomaly detection and policy-controlled remediation. Machine learning and automated recovery remain roadmap items rather than production guarantees.

AWS infrastructure must be reviewed for permissions and cost before deployment. No cloud resources are created by this README.

## License

See [LICENSE](LICENSE) for the original Apache License 2.0. The existing license and Git history are preserved.
