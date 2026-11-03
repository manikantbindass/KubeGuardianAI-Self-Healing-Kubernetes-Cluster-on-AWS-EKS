# Offline Argo CD schemas

`application.json` and `appproject.json` are the v1alpha1 OpenAPI schemas extracted from Argo CD **v3.5.7** CRDs. Descriptions/titles were removed; validation constraints are retained. Argo CD is Apache-2.0 licensed; see [upstream LICENSE](https://github.com/argoproj/argo-cd/blob/v3.5.7/LICENSE).

| Upstream file | SHA-256 of original YAML |
| --- | --- |
| [application-crd.yaml](https://github.com/argoproj/argo-cd/blob/v3.5.7/manifests/crds/application-crd.yaml) | `5dde0e229249b6b707beb98674c1deae3949d5c319a6c45b9f5a80c99618e40c` |
| [appproject-crd.yaml](https://github.com/argoproj/argo-cd/blob/v3.5.7/manifests/crds/appproject-crd.yaml) | `ab225266944322750136f1198d93786e4a79a0e43c8d149abfba44da30a3eac8` |

These files validate manifests offline; they do not install Argo CD. Review upstream security advisories and compatibility before installing a controller. Schema validation does not test cluster reconciliation.
