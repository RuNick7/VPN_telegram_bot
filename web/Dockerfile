# Build context is the repo root (see docker-compose.yml), matching the other
# images here -- they all need files from outside their own directory.

# Must be >= the `go` directive in web/go.mod. The official images set
# GOTOOLCHAIN=local, so a base older than that fails at `go mod download`
# rather than quietly fetching a newer toolchain -- which is the behaviour you
# want, but it does mean the two have to be bumped together.
FROM golang:1.25-alpine AS build
WORKDIR /src

# Dependencies first: this layer is only invalidated when go.mod/go.sum change,
# so ordinary code edits do not re-download the module cache.
COPY web/go.mod web/go.sum ./
RUN go mod download

COPY web/ ./
# CGO off produces a static binary, which is what lets the final stage be
# scratch-thin. -trimpath keeps build paths out of the binary.
RUN CGO_ENABLED=0 go build -trimpath -ldflags="-s -w" -o /out/server ./cmd/server

FROM alpine:3.20
# TLS roots for YooKassa and the panel; tzdata so timestamps are not all UTC
# in logs read by a human in Moscow.
RUN apk add --no-cache ca-certificates tzdata && adduser -D -u 10001 app
USER app
WORKDIR /app
COPY --from=build /out/server /app/server

EXPOSE 8080
ENTRYPOINT ["/app/server"]
