# Reproducibility protocol

**Document role:** executable validation procedure.

## Artifact identification

Record the immutable commit before testing:

```bash
git rev-parse HEAD
git status --short
```

Use a clean checkout of the `CAPO` branch. A branch name alone is not a
reproducible artifact because it can move.

## Reference toolchains

| Area | Reference |
|---|---|
| Python | 3.11; project metadata allows 3.11–3.12 |
| Gateway/Console | Node.js 22.23.2 and npm 10.9.10; Console declares pnpm 11.13.1 |
| Runtime | Rust stable |
| Containers | Docker Engine with Compose v2 |
| Native acceptance | Compatible Linux host with systemd |

Pin dependency lockfiles and report any dependency-resolution failure. Do not
substitute a static check for a blocked compilation or runtime test.

The pinned Node publisher image/archive still bundles npm 10.9.8. Canonical
Node Docker stages and CI explicitly patch the tool to npm 10.9.10 and assert
its active version; this does not mean the original base-image scan is clean.
For a user-owned host installation, follow the prefix-safe setup in
`CONTRIBUTING.md` before locked application installs. Do not upgrade system
prefixes implicitly or confuse the declared npm pin with a measured image scan.

Node image builds accept `--build-arg ALPINE_MIRROR=kernel` when the publisher
CDN is unreachable locally. The default is `cdn`; only the listed HTTPS
kernel.org mirror is accepted, with the same release paths and signing keys.
Unknown values fail closed. Apply the flag to one Gateway/Console build at a
time; it does not change host DNS, bypass TLS/signatures, pin OS-package versions,
or establish live-stack acceptance. Retain transport failures alongside retries.

Console uses TypeScript 5.9.3 for Zod 4's supported TypeScript range. Its
`pnpm-lock.yaml` is canonical; the secondary npm lock is maintained separately
and an npm dry-run is not evidence of a real pnpm installation. Use
`corepack pnpm` when the global pnpm differs from the declared version; enabling
host-wide Corepack shims is not required for that invocation.

Keep `minimumReleaseAgeStrict: true` in the Console workspace. Do not accept
automatically generated release-age exclusions to force a fresh version through;
select a reviewed eligible release or report the install as blocked. Keep npm
and pnpm owner-scoped overrides synchronized: modern named Minimatch/Glob APIs
must not be imposed on legacy callable/callback consumers, or vice versa.
The P4 acceptance report records actual config, matcher and schema regressions.

Console explicitly anchors Next file tracing to the repository root derived
from `next.config.mjs`, including local workspace packages. Do not remove
unrelated ancestor lockfiles to suppress root-inference warnings. After changing
this setting, validate a production build and its generated trace paths, not
only the config object's value; this does not replace a container acceptance run.

`pnpm --dir console prisma:generate` no longer implicitly enables Prisma's
missing-engine-checksum opt-out. Keep skip/ignore flags unset during acceptance;
missing checksum/download access must be reported as blocked, not bypassed.
Cached engine generation is not evidence of a fresh verified engine download.

For compiled Go tools such as esbuild, registry audit results and a scanner
exit zero do not establish stdlib coverage. Require an actual `gobinary` result
with identified stdlib metadata. Publisher esbuild 0.28.x binaries can omit Go
build information; keep this gate unavailable/red rather than treating no
analysis as no findings. See the dated P4 acceptance report before any claim of
remediation, custom source rebuild or new image acceptance.

An auditable esbuild candidate can be built separately from Console after
approval using the pinned Stage A tool. It requires Docker, Node, readelf and a
fresh Trivy 0.76.1 database. Use a **new** absolute private directory outside the
repository; it never updates an existing dependency installation or database:

```bash
python3 scripts/build_auditable_esbuild.py --run --compiler-image \
  --work-dir /absolute/private/path/new-esbuild-run \
  --trivy /absolute/path/to/trivy \
  --trivy-cache /absolute/path/to/existing-fresh-trivy-cache
```

`--compiler-image` explicitly chooses the digest-pinned official Go 1.27.4
image; without it the original pinned compiler archive is required. The direct
archive returned 404 locally. Optional `--compiler-archive` / `--source-archive`
reuse operator-supplied archives only if their original pinned SHA256 matches.
No system-wide Go install, compiler patch, insecure TLS or checksum bypass is
used. Receipts/logs stay in the work directory; outputs and failed attempts are
preserved. Stop conditions remain available RAM below 1 GiB or disk below 3 GiB.
The tool returns nonzero for failed/blocked gates and requires positive Go
metadata/scan coverage, a fresh DB, a repeat-build digest and upstream Go tests.
Passing Stage A alone is not Console integration or final Docker acceptance.
See the [reviewed plan and limits](../capo/p4-esbuild-provenance-plan.md).

For a constrained host, image mode also accepts `--scratch-dir` pointing to an
existing absolute, caller-owned, mode-700 directory outside the repo. It may use
an existing executable RAM filesystem, but requires 512 MiB initially free;
execution stops below 64 MiB scratch space, 1 GiB available host RAM, or 3 GiB
free on the primary output filesystem. Go caches, module cache and temporary
test executables use that directory. No mount flags are changed: a `noexec`
scratch filesystem is rejected. RAM-backed storage is volatile and is not a
backup. A new scanner DB may separately use non-executable RAM storage for data
only, with memory monitoring; the tool never refreshes a shared DB itself.

On hosts without the reference Python tools, use the repository validation
image. It installs the hash-pinned dependency graph from
`control/requirements.validation.lock` and runs as an unprivileged user:

```bash
make python-validation-test
make python-validation-lint
```

Regenerate the lock only as a reviewed dependency update. The target runs the
resolver in Docker and does not install `uv` on the host:

```bash
make python-validation-lock
```

## Validation sequence

### 1. Repository architecture

```bash
python -m pytest tests/architecture -q
```

This checks canonical ownership and selected dependency boundaries. It does not
start services or test operating-system isolation.

### 2. Gateway

```bash
npm ci --prefix gateway
npm run build --prefix gateway
npm test --prefix gateway
```

Capture build/test exit codes and the number of executed tests. Network access
may be required for a fresh dependency install.

### 3. Console

```bash
corepack enable
pnpm --dir console install --frozen-lockfile
pnpm --dir console prisma:generate
pnpm --dir console test -- --config vitest.config.mts
pnpm --dir console build
```

The production build validates compilation and route generation. Browser,
authentication, RTL, and live-stream behavior require separate end-to-end
evidence.

### 4. Runtime

```bash
cargo fmt --check --manifest-path runtime-daemon/Cargo.toml
cargo test --manifest-path runtime-daemon/Cargo.toml --all-targets
```

Current negative-path tests expect unavailable isolation backends to fail
closed. A passing test suite is not evidence of successful namespace/seccomp
isolation until those backends and host-level escape tests are implemented.

### 5. Deployment model

```bash
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml config
```

Compose rendering checks syntax and interpolation only. A running acceptance
test must separately establish health, request flow, persistence, cleanup,
rollback, and secret handling.

## Experimental benchmark blueprint

For each architecture variant and workload:

1. warm dependencies and record hardware/software state;
2. run an explicit warm-up period;
3. execute enough independent repetitions for confidence intervals;
4. report median, p95, p99, throughput, errors, queue time, and resource use;
5. separate external model/tool time from OMERTAOS governance overhead;
6. randomize run order or explain why it is fixed;
7. publish workload definitions, seeds, raw observations, and analysis code.

At minimum, include short tool calls, long model calls, concurrent multi-tenant
loads, denied requests, cancellation, dependency failure, and worker loss.

## Result template

```text
Commit:
Environment:
Command:
Exit code:
Passed / failed / skipped:
Duration:
Warnings or blockers:
Artifacts:
Interpretation:
```

Never omit a failed or skipped gate from a summary. Redact credentials, tokens,
prompts containing personal data, and infrastructure secrets.
