FROM golang:1.26.8-bookworm AS builder
WORKDIR /src
COPY operator/go.mod operator/go.sum ./
RUN go mod download
COPY operator/ ./
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /manager ./cmd/manager

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=builder /manager /manager
USER 65532:65532
EXPOSE 8081
ENTRYPOINT ["/manager"]
