FROM golang:1.26.10-bookworm@sha256:23ce71337b726608afb1bc00986e630a05034a87a87ea1fc2cd1ae5cf33387eb AS builder
WORKDIR /src
COPY operator/go.mod operator/go.sum ./
RUN go mod download
COPY operator/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /manager ./cmd/manager

FROM gcr.io/distroless/static-debian12:nonroot@sha256:afa5c872c891853ca7fcf1f12c3edb23f7eeef36189728842dd51042ff57f7ab
COPY --from=builder /manager /manager
USER 65532:65532
EXPOSE 8081
ENTRYPOINT ["/manager"]
