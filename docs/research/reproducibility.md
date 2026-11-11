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

The approved downstream recipe now applies the pinned `module_update` using
native Go tools: x/sys v0.44.0 and minimum module Go 1.25.0, with the compiler
still Go 1.27.4 and esbuild still 0.28.2. Original/updated go.mod and go.sum
digests, sumdb checksums and rejection of unrelated source edits are mandatory.
This intentionally differs from upstream's old-Go compatibility contract.
The old consumer binary/archive pins are not automatically updated by this
recipe change; a newly built candidate needs its own verified evidence before
promotion. A clean registry audit is not that evidence.

The clean `60ca943` limited run now supplies that candidate-only evidence:
equal builds with SHA256
`b42f2f5152ca473b735aafe681f65589f1b5462c7790787f7173e3103d32ce7e`, 16 upstream
test packages passed, positive stdlib/x/sys scan coverage and a zero-finding raw
scan with a database under 24 hours old. The dated acceptance report includes
exact argv, timings and receipt paths. The active consumer manifests below
still select the previous binary; they are not evidence of installing this
new candidate. Until approved promotion aligns the identities/locks/contexts,
the new CI producer recipe is not a validated end-to-end consumer chain.

The recorded Linux x64 candidate also has a dependency-free identity check:

```bash
node --test tests/tooling/verify_esbuild_artifact.test.mjs
node scripts/verify_esbuild_artifact.mjs /absolute/private/path/build-1/esbuild
```

`scripts/esbuild-linux-x64-artifact.json` pins the separately reviewed build's
size, SHA256, source and compiler identity. The verifier requires a canonical
absolute path, trusted parent permissions, a non-writable executable regular
file, matching platform/ELF bytes/digest and a bounded matching `--version`.
Missing or changed inputs exit nonzero without upstream fallback. It is a
known-artifact identity check, not a generic Go metadata parser or signature
verifier. Exit zero does **not** mean security acceptance: the current output
explicitly says `security_accepted: false` and retains CVE-2026-39824.
It neither installs the candidate nor runs a consumer command. The manifest is
trusted local input; these checks do not defend against a malicious same-UID
owner/root replacing it or changing the binary after verification. The
controlled Console integration below is Linux x64 only; production tool
ownership and final image acceptance remain open.

Prepare a separate locally named provider for **isolated** installer validation:

```bash
node scripts/prepare_esbuild_provider.mjs \
  /absolute/private/path/build-1/esbuild \
  /absolute/verified-source/LICENSE.md /absolute/private/parent/new-provider
```

The output parent must already be canonical, caller-owned and private (700);
the output must not exist or be inside this repository. The script verifies
the binary and pinned source-license digest, preserves the license, creates a
private package with unsigned provenance and never installs/publishes it.
`npm pack /absolute/private/parent/new-provider --json --pack-destination=/absolute/private/artifacts`
can then create a local tarball. Normal npm packaging changes executable mode
to 755; keep the actively executed tool separately protected, not by chmodding
shared installed/store hardlinks.

The isolated 2026-11-11 fixture first proved these **scoped** overrides with both
native lock generators. npm uses `overrides["esbuild@0.28.2"]["@esbuild/linux-x64"]`, pnpm uses
workspace `overrides["esbuild@0.28.2>@esbuild/linux-x64"]`, each set to
`file:../artifacts/omerta-esbuild-linux-x64-0.28.2-omerta.1.tgz`. Fresh fixtures
used esbuild 0.28.2, tsx 4.23.15 and Vite 7.3.7. Native `npm ci` and
`pnpm install --frozen-lockfile` passed without lock changes; build scripts and
optional dependencies remained enabled. See the dated acceptance report and
its retained exact container argv/manifests for reproduction.

`scripts/probe_esbuild_installation.mjs` is a restricted diagnostic for those
named fixtures, not an install hook or general consumer wrapper. Its container
requires the protected tool at `/opt/omerta-tools/esbuild`, verifier/manifest
beside the probe under `/inputs/`, and `/inputs/esbuild-publisher-package.json`
extracted from the original SRI-verified JS tarball. It checks CLI/API override,
async spawn path, sync transform, tsx ESM/CJS, Vite transform and installed ELF
inventory. All probe output retains `security_accepted: false`; the existing
advisory and full Console/image acceptance remain open.

### Controlled Console compiler input

The authorized integration now pins both Console locks to esbuild 0.28.2 and
the independent Linux x64 provider. Its canonical file reference is
`file:../artifacts/tooling/esbuild/omerta-esbuild-linux-x64-0.28.2-omerta.1.tgz`.
The provider is also a required direct dev dependency: npm 10.9.10 can silently
omit a relative file override on an existing optional edge, even when its lock
command exits zero. The explicit dependency prevents accepting that incomplete
graph. Keep the publisher's JS SRI and binary hashes unchanged.

Neither the executable nor tarball is committed. After separately producing
the reviewed candidate/provider, stage the input into a **new** absolute,
private directory outside this repository, then copy only the pinned archive
data into the ignored workspace path:

```bash
export OMERTA_ESBUILD_CONTEXT=/absolute/private/parent/new-esbuild-context
node scripts/stage_esbuild_context.mjs \
  /absolute/private/path/build-1/esbuild \
  /absolute/private/artifacts/omerta-esbuild-linux-x64-0.28.2-omerta.1.tgz \
  "$OMERTA_ESBUILD_CONTEXT" --workspace "$PWD"
node console/scripts/with-auditable-esbuild.mjs pnpm --dir console install --frozen-lockfile
pnpm --dir console test --config vitest.config.mts --maxWorkers=1 --no-file-parallelism
```

For an existing verified context use
`node scripts/stage_esbuild_context.mjs --link-workspace "$OMERTA_ESBUILD_CONTEXT" "$PWD"`.
Staging checks independent binary/archive pins, refuses overwrite of changed
data or symlink destinations, and does not chmod the checkout or installed
packages. The default context is
`$HOME/.local/share/omerta-tools/esbuild/linux-x64-0.28.2-omerta.1`.
`OMERTA_ESBUILD_BINARY` selects an explicit protected binary instead; a
conflicting `ESBUILD_BINARY_PATH` is rejected. Standard Console scripts and
Docker entry/install commands verify identity before spawning consumers and
propagate nonzero exits/signals; direct third-party commands outside the
wrapper are not protected by it.

Compose passes this narrow directory as the named `omerta_esbuild` context;
direct Docker builds require `--build-context "omerta_esbuild=$OMERTA_ESBUILD_CONTEXT"`.
The main context excludes `artifacts/`. No broad home/cache mount is required.
CI builds the candidate from pinned source/compiler, requires the raw scan
gate, packs/verifies the input, then transfers it to dependent jobs. A run
reporting the recorded UNKNOWN advisory will block that producer: no
suppression, successful remote CI, ARM artifact or final image acceptance is
claimed. The ARM matrix is retained and cannot use this x64-only input.
Do not run heavy Console/image exports below the 15 GiB planning budget, or
workloads below 1 GiB available host RAM. Validation installs in private mirrors
do not update running images or the original checkout's node_modules; an
operator reinstall in the checkout does update its dependencies. Rolling back requires a
reviewed revert of the integration and a locked reinstall/rebuild of affected
Console tooling, not a database or volume change.

The full Console pnpm installation and 48 collected tests passed in the dated
controlled-integration run. The initial full npm attempts timed out on the
registry or hit default noexec; those failed receipts remain recorded. The
subsequent **executable disk-backed** clean `npm ci --include=dev
--prefer-offline --fetch-timeout=120000 --fetch-retries=1` passed without changing
either lock or the manifest. It reused only the task-owned disposable fixture,
after a compressed snapshot and complete content comparison of its previous
generated dependencies; no checkout dependencies, caches or volumes were
deleted. Installed CLI/API/tsx/Vite, guarded Prisma generation and a separate
zero-finding npm audit passed. This is full npm installation/selected-consumer
evidence, not a second 48-test run, a clean Go scan or final image acceptance.

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
