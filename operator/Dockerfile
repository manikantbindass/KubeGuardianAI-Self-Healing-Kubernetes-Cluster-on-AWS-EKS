FROM golang:1.26.8-bookworm@sha256:dc9ad6c05acc7a88e5b71bde60a5fe3bd4b9f0db209011711b464107438a8107 AS builder
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
