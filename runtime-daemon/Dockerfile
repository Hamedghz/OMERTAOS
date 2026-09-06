FROM rust:1.87-bookworm@sha256:251cec8da4689d180f124ef00024c2f83f79d9bf984e43c180a598119e326b84 AS builder

ENV CARGO_BUILD_JOBS=1

WORKDIR /app
RUN apt-get update \
    && apt-get install -y --no-install-recommends protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*
COPY schemas/v1/protos ./schemas/v1/protos
COPY runtime-daemon ./runtime-daemon
WORKDIR /app/runtime-daemon
RUN cargo build --locked --release

FROM debian:bookworm-slim@sha256:88200866dfff7ea7f5cbcb6ec7c8a701889efe6fe859fe64d6990e4b07ea4171

RUN useradd --system --uid 10001 --create-home runtime \
    && install -d -o runtime -g runtime -m 0700 /var/lib/omerta/runtime
COPY --from=builder /app/runtime-daemon/target/release/runtime-daemon /usr/local/bin/runtime-daemon

USER runtime
EXPOSE 50051
ENTRYPOINT ["/usr/local/bin/runtime-daemon"]
