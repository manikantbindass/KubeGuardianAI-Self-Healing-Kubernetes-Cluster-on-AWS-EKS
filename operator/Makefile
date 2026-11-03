.PHONY: generate test vet build
generate:
	go run sigs.k8s.io/controller-tools/cmd/controller-gen@v0.20.1 object paths=./api/v1alpha1 crd:crdVersions=v1 output:crd:artifacts:config=crds
test:
	go test ./... -count=1
vet:
	go vet ./...
build:
	go build -trimpath -o ../.cache/operator/manager ./cmd/manager
