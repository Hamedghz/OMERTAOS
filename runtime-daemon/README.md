# Runtime Daemon

**Document role:** Runtime ownership contract with an explicit implementation
gate.

The Runtime Daemon is the intended Rust execution boundary for OMERTAOS agents.
The current prototype exposes the canonical server and named capability checks,
but it does not yet execute work in a completed isolated sandbox. Unsupported
isolation paths fail closed, as described under **Current execution gate**.

```text
gRPC admission → grant verification → bounded job queue → worker
               → sandbox + resource limits → command/tool adapter
               → audit/result stream → cleanup
```

Target responsibilities include sandbox creation, process and command
execution, filesystem/network/device capability enforcement,
CPU/memory/time/process limits, cancellation, output bounds, cleanup, and
tamper-evident audit records. It does not authenticate end users, plan tasks, or
choose agents/models.

The target security model is deny-by-default. A job must carry a valid
signature, audience, expiry, task/attempt binding, lease token, executable
allowlist, path/network rules, and resource ceilings. A completed Linux backend
would combine namespaces, cgroups, mount restrictions, seccomp, and privilege
dropping; platform-specific backends must provide equivalent semantics or
reject unsupported grants.

The daemon targets low queue overhead and high throughput through Tokio asynchronous I/O, bounded multi-thread scheduling, backpressure, streaming output, prevalidated sandbox templates, and separate pools for workload classes. Performance never bypasses grant verification or cleanup.

Build and test:

```bash
cargo build --manifest-path runtime-daemon/Cargo.toml --release
cargo test --manifest-path runtime-daemon/Cargo.toml
```

The local quickstart builds the daemon as the `runtime` service and binds gRPC to
`127.0.0.1:50051`. Containers reach it at `runtime:50051`. Override
`AION_RUNTIME_BIND_ADDR` only when running the binary outside Compose.
The container healthcheck uses `runtime-daemon --healthcheck` to verify that the
configured gRPC listener accepts connections before dependent services start.

`ExecuteCommand` requires node-bound lease metadata with a bounded expiry and a
monotonic generation. Runtime verifies the metadata HMAC using a dedicated key
loaded from `OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE` (preferred) or
`OMERTA_RUNTIME_LEASE_HMAC_KEY`. Setting both sources, or supplying missing,
invalid, or mismatched key material, fails closed. The key must be base64
encoding of 32-64 random bytes and must match Control without reusing an
administrator or encryption credential.

When `AION_RUNTIME_LEASE_STATE_PATH` is configured, Runtime atomically persists
only a hashed tenant/task identity, generation, and expiry. Quickstart mounts
`runtime-state` at `/var/lib/omerta/runtime`, so repeated or older admissions
remain fenced after a normal daemon restart. A malformed or unavailable state
file fails startup/admission closed; the raw lease token is never persisted or
logged. State is local to one Runtime node and must not be shared by concurrent
workers. `AION_RUNTIME_LEASE_MAX_TTL_SECONDS` defaults to 120 seconds.

This is authenticated lease metadata inside the prototype service network, not
caller identity, mTLS, cancellation of work already admitted under an older
lease, or a distributed fencing protocol.

Expose the gRPC listener only on the internal service network and require mTLS in production.

## Current execution gate

The canonical server, capability checks and health endpoint are available, but
the Linux namespace, mount, seccomp and isolated-process backends are not yet
implemented. Execution therefore fails closed instead of returning a synthetic
PID or command success. Do not treat gRPC readiness as sandbox acceptance.

The former compatibility Runtime crate was retired in Structure S5. This crate
is now the sole Runtime implementation and binary owner.
