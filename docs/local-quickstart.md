# Local Docker quickstart

OMERTAOS provides two canonical local Compose entry points. `deploy/docker/compose/quickstart.yml` is the primary, minimal stack. `deploy/docker/compose/local.yml` exposes additional infrastructure ports for development and keeps Vault behind an optional profile. Use `--project-directory .` from the repository root so build contexts and bind mounts remain repository-relative.

## Requirements

- Docker Desktop on Windows/macOS, or Docker Engine with Compose v2 on Linux
- At least 8 GB of available memory
- Free host ports 3000 and 8080, plus loopback-only 8000 and 50051 for quickstart
- For the extended local stack, also free ports 5432, 6379, 27017, 6333, 9000, and 9001

Confirm that the Docker daemon is running before starting:

```bash
docker version
docker compose version
```

## Environment setup

Create a local environment file from the development defaults:

```bash
cp dev.env .env
chmod 0600 .env
python3 scripts/validate_environment_aliases.py --migrate-env-file .env
python3 scripts/validate_environment_aliases.py \
  --env-file .env --reject-legacy-secrets
```

On PowerShell:

```powershell
Copy-Item dev.env .env
```

The checked-in values are local placeholders only. The migration command removes
equal deprecated aliases, renames non-secret old-only settings, and refuses to
copy an old-only secret. Do not use placeholder values in production or expose
the development services publicly.

## Quickstart

```bash
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml config
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml build
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml up -d
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml ps
```

Expected host ports:

| Service | URL |
|---|---|
| Console | `http://localhost:3000` |
| Control | `http://localhost:8000` (loopback only) |
| Gateway | `http://localhost:8080` |
| Runtime gRPC | `127.0.0.1:50051` |

The defaults remain unchanged. When another local stack must stay running, use
a distinct Compose project, network, image name, and host ports for every
command in the build/up/down sequence:

```bash
export OMERTA_DOCKER_NETWORK=omerta-r5-net
export OMERTA_RUNTIME_HOST_PORT=55051
export OMERTA_CONTROL_HOST_PORT=18000
export OMERTA_GATEWAY_HOST_PORT=18080
export OMERTA_CONSOLE_HOST_PORT=13000
export OMERTA_CONSOLE_IMAGE=omertaos-r5-console
export OMERTA_RUNTIME_IMAGE=omertaos-runtime
export NEXTAUTH_URL=http://localhost:13000
export NEXT_PUBLIC_GATEWAY_URL=http://localhost:18080
export OMERTA_CORS_ORIGINS=http://localhost:13000

docker compose --project-name omertaos-r5 --project-directory . \
  -f deploy/docker/compose/quickstart.yml config
```

Use the same variables and `--project-name` when inspecting or stopping that
stack. Internal service addresses such as `runtime:50051`, `control:8000`, and
`gateway:8080` do not change. On resource-constrained hosts, build Runtime,
Control, Gateway, and Console one at a time, then run `up -d` without `--build`.

Runtime readiness is checked from inside its container before Control starts.
The one-shot Console installer runs after PostgreSQL is healthy, and Control
waits for it to finish so Prisma migrations cannot race Control's additive
table initialization.
Quickstart also enables a bounded Control-owned Runtime lifecycle supervisor.
After a successful Runtime gRPC readiness probe, it registers the configured
node or bounded node list and refreshes heartbeats sequentially every 10
seconds. The node id, capabilities, tenant eligibility, declared capacity,
heartbeat interval, and probe timeout are configurable through the
`OMERTA_RUNTIME_*` values in `.env.example`. `OMERTA_RUNTIME_NODES_JSON` is an
optional trusted Control-owned list; when blank, the original single-node
settings remain active. `OMERTA_RUNTIME_MANAGED_NODE_LIMIT` defaults to 2 and is
bounded to 32. The interval is limited to 20 seconds so it remains below the
current 30-second stale-worker threshold. Stopping Runtime stops its heartbeats
and causes scheduling to fail closed after that threshold; restarting Runtime
restores eligibility without an operator registration call.

For an already registered managed node, each successful probe reconciles the
trusted capability, tenant-eligibility, and declared-capacity configuration.
The probe does not report Runtime lease usage, so it preserves Control's active
lease count rather than resetting it.

Control issues short-lived execution leases with a default 45-second TTL and
reclaims expired capacity during lifecycle synchronization or the next
scheduling transaction. Runtime accepts the first valid generation for a
tenant/task pair and rejects missing, expired, repeated, older, or wrong-node
lease metadata. `OMERTA_RUNTIME_LEASE_TTL_SECONDS` is bounded to 5-120 seconds;
`OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS` bounds Runtime admission and defaults to
120 seconds. Keep the Control TTL above the execution timeout and at or below
the Runtime maximum. The process-side `AION_RUNTIME_TIMEOUT_SECONDS` alias is
still pending migration in M3 and is not a canonical operator setting yet.

Before starting execution-capable services, provision one dedicated secret file
and set `OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE` in `.env` to its host path. The file
must contain base64 encoding of 32-64 random bytes, be readable only by the local
operator, and is mounted read-only into Control and Runtime. For example, create
the ignored `.secrets-out/runtime-lease-hmac-key` with mode `0600` and write the
output of `openssl rand -base64 32` directly to it; never paste the value into
logs, chat, source control, `.env`, or command history. Do not reuse the Gateway
admin token, database password, or Control local encryption key. The direct
`OMERTA_RUNTIME_LEASE_HMAC_KEY` environment source remains available outside the
canonical Compose path for development compatibility, but production should use
an external secret manager with audited access and rotation.
Quickstart stages the file through a one-shot init service into a Docker volume
as UID 10001 with mode `0400`, then mounts that volume read-only. This preserves
the non-root Runtime boundary without making the host secret world-readable.
Quickstart persists the Runtime generation fence in the `runtime-state` volume;
normal `stop`/`start` or container recreation preserves it. Do not use
`docker compose down -v`.

This local supervisor is not a distributed membership protocol. Runtime does
not receive an administrator token or self-authorize tenant eligibility, and
operator-requested draining remains authoritative. The lease HMAC authenticates
Control-issued dispatch metadata but is not caller identity or a replacement
for authenticated transport. The Quickstart gRPC boundary remains an
internal-network prototype, and production still requires workload identity or
mTLS.

### Two-worker acceptance profile

The second worker is opt-in and intended for constrained local acceptance. It
reuses the selected Runtime image, publishes no additional host port, and
configures two trusted local nodes with separate tenant/capability/capacity
declarations:

```bash
export OMERTA_RUNTIME_IMAGE=omertaos-runtime

docker compose --env-file .env --project-directory . \
  --project-name omertaos-two-workers \
  -f deploy/docker/compose/quickstart.yml \
  -f deploy/docker/compose/quickstart.two-workers.yml config

docker compose --env-file .env --project-directory . \
  --project-name omertaos-two-workers \
  -f deploy/docker/compose/quickstart.yml \
  -f deploy/docker/compose/quickstart.two-workers.yml up --no-build -d
```

Build required service images one at a time before `up --no-build`. The profile
demonstrates bounded local scheduling behavior only; it is not a benchmark or
evidence of horizontal scalability, distributed membership, or production
readiness.
Bootstrap passwords default to a configurable 8-32 character policy. Override
`CONSOLE_ADMIN_PASSWORD_MIN_LENGTH` and `CONSOLE_ADMIN_PASSWORD_MAX_LENGTH`
when a longer local credential is required; the minimum cannot be lower than 8
and the maximum cannot exceed 72.
Control readiness uses Python's standard-library HTTP client, so its image does
not install an extra system curl package solely for health checks.

Check health with:

```bash
curl -f http://localhost:8000/health
curl -f http://localhost:8000/v1/health
curl -f http://localhost:8080/health
curl -f http://localhost:3000/
```

Run the read-only Quickstart acceptance probe against the same Compose project
and exported host-port variables used to start the stack:

```bash
bash deploy/native/scripts/smoke-test.sh --mode quickstart \
  --project-name omertaos-r5
```

The probe checks the selected project's PostgreSQL, Redis, Runtime, installer,
Control, Gateway, and Console containers, verifies a fresh automatic Runtime
registration, and then checks the HTTP health chain. It does not start,
restart, migrate, bootstrap, or stop services.

For the two-worker profile, also run the secondary binary healthcheck:

```bash
docker compose --env-file .env --project-directory . \
  --project-name omertaos-two-workers \
  -f deploy/docker/compose/quickstart.yml \
  -f deploy/docker/compose/quickstart.two-workers.yml \
  exec -T runtime-secondary /usr/local/bin/runtime-daemon --healthcheck
```

Stop the stack with the same project/files and `docker compose ... stop`.
This preserves containers, logs, and named volumes. Never add `-v` when state
must be retained.

## Extended local stack

The canonical extended local entry is:

```bash
docker compose --project-directory . -f deploy/docker/compose/local.yml config
docker compose --project-directory . -f deploy/docker/compose/local.yml up -d
```

Vault is optional and starts only when explicitly selected:

```bash
docker compose --project-directory . -f deploy/docker/compose/local.yml --profile vault up -d
```

The historical `kernel/` service is disabled because that directory and Dockerfile are not present. The canonical `runtime-daemon/` runs as the `runtime` service and exposes its gRPC endpoint on loopback port 50051 for local development.

## Common errors

### Missing Dockerfile

Run `docker compose ... config` and verify that each build uses the repository root as its context and an existing service Dockerfile. Do not create an empty service solely to satisfy Compose.

### Missing environment values

Recreate `.env` from `dev.env`. `docker compose ... config` shows the resolved values and reports unset variables.

### Port already in use

Stop an older Compose project only when you own it and intend to stop it. When
it must remain available, use the isolated project, network, port, image, and
URL overrides shown above. Do not attach independent Quickstart runs to the
same explicitly named Docker network.

### Kernel path not found

Use `deploy/docker/compose/quickstart.yml` or `deploy/docker/compose/local.yml`; these entry points do not reference the removed `kernel/` path. The primary quickstart includes the canonical Rust runtime.

### Gateway cannot reach Control

Inside containers the Gateway must use `http://control:8000`, never `localhost:8000`. Inspect `docker compose ... logs control gateway` and confirm the Control healthcheck is healthy.

### Console cannot reach Gateway

Browser code uses `NEXT_PUBLIC_GATEWAY_URL=http://localhost:8080`. Server-side Console code uses `GATEWAY_URL=http://gateway:8080`. Mixing these two address spaces causes connection failures.
