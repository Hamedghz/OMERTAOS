# CAPO acceptance report

## M4.1.2 Pinned images and bounded live acceptance - 2026-09-06

Branch: `Radin/omerta-env-namespace`; baseline: `62fdfed`;
checkpoint: `checkpoint/m4-1-2-start-62fdfed`.
Builds used this baseline plus the digest-pin working-tree changes recorded
with this report. No source changes were made during the builds.

Seven upstream Quickstart references and all base-image references in the four
application Dockerfiles are pinned to SHA-256 digests. Pins preserve locally
tested images; the optional Xray index digest was obtained from the registry.
Xray was not started. `.secrets-out/` is now excluded from Docker build context;
earlier context exclusion was incomplete, but this is not evidence that a key
was copied into an application image. Existing caches were not purged.

| Gate | Actual result |
|---|---|
| Focused image/toolchain and Quickstart contracts | 17 passed, exit 0, 0.54s |
| Compose rendering, including isolated image override | Exit 0; no environment values printed |
| Control build | Exit 0; BuildKit duration 15.2s |
| Runtime locked release build | Exit 0; BuildKit duration 15m 26s; one Cargo job |
| Gateway locked build | Exit 0; BuildKit duration 4m 29s |
| Console frozen-lockfile build | Exit 0; BuildKit duration 21m 41s; 21 pages and bootstrap compiler completed |
| Isolated stack readiness | Exit 0, 123.2s; Compose parallel limit 1 and one Runtime |
| Running Gateway package verification | Exit 0, 0.8s; Fastify 5.12.3, fast-uri 4.1.4 |
| Mongo ping | Exit 0, 8.6s |
| Qdrant/MinIO readiness and existing Qdrant fixture | Exit 0, 3.3s; prior fixture retained across container recreation |
| Single final native-script Quickstart smoke | Exit 0, 21.5s; 13 checks passed |
| Normal shutdown | Exit 0; all 11 containers stopped and six volumes retained |

The final smoke covers PostgreSQL, Redis, installer completion, Runtime health
and automatic registration, Control, Gateway dependencies, Console and the
Console -> Gateway -> Control health chain. It is not an authenticated task
execution test; full task/parity/restore acceptance remains in later subphases.
No repeated application test suites were run after the user's batching request.
The final acceptance ran once. No second Runtime, benchmark, live systemd test,
image vulnerability scan or optional proxy acceptance was performed.

Resource guards polled available RAM during the Console build and acceptance.
No guard triggered; minimum sampled RAM during live acceptance was 2865 MiB.
Qdrant exited 143 on requested shutdown; other project containers exited 0.

Warnings/negative evidence: Cargo index timeouts recovered without changing
the lockfile or TLS controls; npm emitted existing deprecated-tool warnings;
Console reported stale Browserslist data. The manually provisioned Qdrant volume
still lacks Compose labels. One diagnostic image-inspection command contained a
mistyped Redis digest and exited 1; the checked-in pin was correct and live
startup passed. Digest pins do not freeze apt/apk or all transitive Python
resolution, and no bit-for-bit or production-security claim is made.

Local image IDs (not published registry artifacts):

| Tag | SHA-256 image ID |
|---|---|
| `omertaos-control:m412-62fdfed` | `e40d4d92021723de368fa4544c172e3b1148ab98505c5c7b7d72b2315663c36c` |
| `omertaos-runtime:m412-62fdfed` | `c83cbcd5a9b5126614bc20e446b01777c0032735941875b2afb87b70245e066c` |
| `omertaos-gateway:m412-62fdfed` | `477ba0891a67a301aa91bb03431219bdc07b0e3b9e46e247c90c888c844d8502` |
| `omertaos-console:m412-62fdfed` | `4bb2d109a3f3da333f1dbdf1cc68f8064d18c9aa4a66d1dcab46df9a5b97eaad` |

Build commands, run sequentially from the repository root:

```bash
docker build --progress=plain -f control/Dockerfile -t omertaos-control:m412-62fdfed .
docker build --progress=plain -f runtime-daemon/Dockerfile -t omertaos-runtime:m412-62fdfed .
docker build --progress=plain -f gateway/Dockerfile -t omertaos-gateway:m412-62fdfed .
docker build --progress=plain -f console/Dockerfile -t omertaos-console:m412-62fdfed .
```

The local override `/tmp/omerta-m412-62fdfed.compose.yml` contains:

```yaml
services:
  control:
    image: omertaos-control:m412-62fdfed
  gateway:
    image: omertaos-gateway:m412-62fdfed
```

For this isolated stack, use the environment and Compose invocation below.
The existing ignored environment file and Runtime secret must be provisioned.
Start only with at least 1 GiB available RAM, monitor during execution, and
stop this project if RAM falls below that threshold.

```bash
export COMPOSE_PARALLEL_LIMIT=1
export COMPOSE_ENV_FILES=/home/omerta/projects/OMERTAOS/.env
export OMERTA_DOCKER_NETWORK=omerta-m4-validation-net
export OMERTA_CONSOLE_HOST_PORT=23000 OMERTA_GATEWAY_HOST_PORT=28080
export OMERTA_CONTROL_HOST_PORT=28000 OMERTA_RUNTIME_HOST_PORT=25051
export OMERTA_RUNTIME_IMAGE=omertaos-runtime:m412-62fdfed
export OMERTA_CONSOLE_IMAGE=omertaos-console:m412-62fdfed
export OMERTA_CORS_ORIGINS=http://localhost:23000 NEXTAUTH_URL=http://localhost:23000
export NEXT_PUBLIC_GATEWAY_URL=http://localhost:28080
compose=(docker compose --project-directory "$PWD" --project-name omerta-m4-validation
  -f deploy/docker/compose/quickstart.yml -f /tmp/omerta-m412-62fdfed.compose.yml)
"${compose[@]}" config --quiet
"${compose[@]}" up -d --no-build --pull never --wait --wait-timeout 120
bash deploy/native/scripts/smoke-test.sh --mode quickstart --project-name omerta-m4-validation --timeout 8
"${compose[@]}" stop --timeout 30
```

Earlier images remain available for rollback. Keep the same project volumes
when selecting previous application image tags. No volume deletion, push,
merge, reset-credit redemption or production deployment occurred.

## M4.1.1 Gateway dependency remediation - 2026-09-06

Baseline/checkpoint: `1d1ed05`, `checkpoint/m4-1-1-start-1d1ed05`.
Branch: `Radin/omerta-env-namespace`.

Fastify's manifest minimum is now 5.12.1; the npm-generated lock resolves
5.12.3, with fast-uri 4.1.4 and all three nested 3.x copies at 3.1.7.
Only these dependency entries changed. Relevant upstream advisories include
[primitive coercion](https://github.com/advisories/GHSA-w2qp-rph6-63g4),
[forwarded-header spoofing](https://github.com/advisories/GHSA-3m5p-2c4r-xxw2),
[repeated hostname decoding](https://github.com/advisories/GHSA-fph4-wmhf-6fwf)
and [scheme normalization](https://github.com/advisories/GHSA-jqff-g426-hqxp).
These identify dependency defects, not proof of application exploitability.

The primitive-schema probe independently reproduced Fastify 5.11.3 handing
the string `"10"` to a handler after integer validation (exit 1). The added
regression verifies the numeric handler value and rejection of an out-of-range
input on the patched dependency.

| Command/gate | Result |
|---|---|
| `npm update fastify fast-uri --prefix gateway --package-lock-only` | Exit 0; targeted lock update, zero reported vulnerabilities |
| `npm ci --prefix gateway` | Exit 0; 408 packages installed in approximately 3 minutes |
| `node gateway/node_modules/vitest/vitest.mjs run tests/gateway/schemaValidation.spec.ts` | Exit 0; 1 passed, 4.32s |
| `npm run build --prefix gateway` | Exit 0 |
| `npm test --prefix gateway` | Exit 0; 26 passed in 9 files, 12.14s |
| `npm audit --prefix gateway --json` | Exit 0; total vulnerabilities 0, 432 dependencies reported |
| Container pytest `tests/architecture/test_javascript_toolchain.py -q -p no:cacheprovider` | Exit 0; 3 passed, 0.36s |
| `git diff --check` | Exit 0 |

Commands used Node 22.23.2 and npm 10.9.8. The host's official Linux x64 Node
archive was downloaded from nodejs.org and checked against its published
SHA-256 (`d60acfe00a2932254bb0ad20e01b0d74397a0875595de719654b214f4b03f307`).
It is installed under `~/.local/opt/node-v22.23.2-linux-x64`; new Bash login
shells report the expected Node/npm versions. Existing process environments
need a new shell or an explicit PATH prefix. The system Node was retained.
The prior Bash configuration is backed up at
`~/.cache/omerta-toolchain/bashrc.before-node-22.23.2`.

Earlier failures: Docker audit attempts were interrupted after stalled network
requests (137); host audit returned ETIMEDOUT (1) and metadata fetch timed out
(124). Retrying the official registry subsequently succeeded. The old local
Vitest installation lacked a native binding (1), resolved by locked `npm ci`.
The first host build could not write root-owned generated `gateway/dist` (2);
ownership of that generated directory alone was corrected to the workspace
user before the successful build. Deprecated ESLint/inflight/glob and related
tooling warnings remain; zero audit findings is not security certification.

No application image was rebuilt and no persistent service was started in this
subphase. The previous Gateway image still contains the previous dependencies;
image rebuild and live acceptance remain pending. Rollback is a reviewed revert
of the manifest, lock and regression change, followed by locked installation;
it would restore the known vulnerable dependencies. No push or merge occurred.

## M4 isolated Docker acceptance - 2026-09-05

Branch: `Radin/omerta-env-namespace`. Checkpoint: `6469f44`
(`checkpoint/omerta-m4-start-6469f44`). Repairs: `073e63c`, `66eb610`,
`e3a4b76`. This is local, single-worker acceptance, not a scalability,
Linux sandbox, native systemd, or production-readiness claim.

The isolated project was `omerta-m4-validation`, with network
`omerta-m4-validation-net` and Console/Gateway/Control/Runtime host ports
23000/28080/28000/25051. Other Compose projects were outside this work.

| Gate | Actual result | Limits |
|---|---|---|
| Sequential application image builds | Control, Runtime, Gateway and Console passed | Gateway install reported one moderate and one high vulnerability; unresolved |
| Console bootstrap compilation | Repaired inherited TypeScript option; rebuilt successfully | Initial build failed with TS5096 |
| Console health aggregation | Repaired internal self-probe URL and degraded aggregation; full Console suite: 32 passed | Test harness required test-mode React and dependencies under `/app` |
| Final architecture suite | 99 passed, 1 deselected; exit 0, 20.92s | Structure completion gate explicitly excluded; not passed |
| Final native contract suite | 75 passed; exit 0, 6.02s | Container-based tests, not live systemd acceptance |
| Focused Quickstart tests | 13 passed; exit 0, 0.55s | Static contract checks supplemented by live checks below |
| Compose config | Exit 0 | Rendering alone is not live acceptance |
| Qdrant readiness | Docker healthy; direct `/readyz` HTTP 200 | Official image has Bash but no curl; probe uses Bash TCP and requires HTTP 200 |
| Qdrant persistence | Fixture point retrieved after forced container recreation | Named volume preserved; fixture retained in isolated test data |
| Final Quickstart smoke | Exit 0; PostgreSQL, Redis, installer, Runtime, registration, Control, Gateway, Console and canonical health chain passed | Read-only smoke does not itself execute a task |
| Authenticated task flow, earlier in M4 | Console -> Gateway -> Control -> Runtime deterministic echo and idempotent replay passed; persisted tenant, scheduling and audit evidence inspected | One Runtime, deterministic echo only |
| Earlier restart checks | PostgreSQL records, Runtime fencing fingerprint and Control registration survived normal restarts; installer rerun retained counts | No crash or host reboot claim |
| Backup pipeline | Nonempty PostgreSQL custom dump and archive listing verified | No isolated restore performed; not full backup acceptance |

Failed attempts remain part of the evidence: the first Console build failed;
host Python lacked pytest; an early read-only container lacked Git metadata;
Console test harness attempts encountered write permissions, module resolution
and production React `act` errors before a corrected full run passed. An early
Runtime metadata assertion expected the wrong GID and was independently rerun
against actual protected metadata. The first Qdrant data copy could not access
the container writable layer via `--volumes-from`; copying the stopped
container's data with `docker cp` succeeded. Its first healthcheck failed
because curl was absent. The final smoke first exited 1 because the environment
file was omitted, then passed with `COMPOSE_ENV_FILES` explicitly supplied.
These failures were not counted as successful gates.

Open limitations: the manually provisioned Qdrant volume has no Compose labels
and causes a warning; it was preserved. Redis warned about host overcommit;
no sysctl was changed. Upstream images still use mutable tags, including
Qdrant `latest`, so exact image reproduction requires digest pinning in a
separate reviewed change. Full old-only versus new-only live-stack parity,
isolated restore, native startup/reboot acceptance and dependency vulnerability
remediation remain open. Do not remove legacy aliases on this evidence alone.

Reproduce focused checks from the repository root (the local ignored environment
file and secret must already be provisioned; never paste their values):

```bash
docker compose --project-directory "$PWD" --project-name omerta-m4-validation \
  --env-file /home/omerta/projects/OMERTAOS/.env \
  -f deploy/docker/compose/quickstart.yml config --quiet
docker run --rm --network none \
  --mount type=bind,src="$PWD",dst=/workspace,readonly --workdir /workspace \
  omertaos-python-validation:m3 python -m pytest \
  tests/architecture/test_quickstart_runtime.py -q -p no:cacheprovider
docker run --rm --network none \
  --mount type=bind,src="$PWD",dst=/workspace,readonly --workdir /workspace \
  omertaos-python-validation:m3 python -m pytest tests/native -q -p no:cacheprovider
# Requires the isolated stack to be running first:
COMPOSE_ENV_FILES=/home/omerta/projects/OMERTAOS/.env \
OMERTA_CONSOLE_HOST_PORT=23000 OMERTA_GATEWAY_HOST_PORT=28080 \
OMERTA_CONTROL_HOST_PORT=28000 bash deploy/native/scripts/smoke-test.sh \
  --mode quickstart --project-name omerta-m4-validation --timeout 8
```

Do not revert the Qdrant volume mount on an existing populated deployment:
rolling back the health probe must preserve `qdrant-data:/qdrant/storage`.
No volume deletion, push, merge, native installation or benchmark was performed.
Final `docker compose stop --timeout 30` exited 0. All eleven project containers
were retained and stopped; Qdrant reported exit 143 following the requested
stop, and the other containers exit 0. All six named project volumes remain.

## R6.15 OMERTA lease namespace and file-backed secret acceptance — 2026-09-03

Branch: `Radin/omerta-env-namespace`

Baseline: `1d9183b` (`feat(runtime): persist authenticated lease fences`)

Implementation commits: `9579bc0`, `127267a`, `d8944e9`, `cfb9c05`,
`29cda45`, and `44329cf`.

This gate moved the canonical execution-lease signing namespace from the
release/branch name to the product identity: `OMERTA_RUNTIME_LEASE_HMAC_KEY`
and `OMERTA_RUNTIME_LEASE_V1`. The preferred input is now
`OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE`; the direct value remains a documented
development compatibility path. Python and Runtime reject absent, malformed,
or conflicting key sources. The local key used for acceptance remained outside
Git and no credential value was printed or committed.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Focused secret/config regression | pass | Python secret-source and lease tests reported `19 passed`; Rust reported `16 passed`; Ruff and Runtime formatting passed |
| Full Python regression | pass with exclusions | `241 passed, 2 skipped, 1 deselected`, with three existing FastAPI/Starlette deprecation warnings and the intentionally red Structure completion gate excluded |
| Architecture regression | pass | Final run reported `74 passed, 1 deselected` in 7.34 seconds |
| Compose rendering | pass | Canonical one-worker and opt-in two-worker configurations both rendered with exit 0; no second worker was started in this gate |
| Non-root secret staging | pass live | The one-shot initializer staged the key into a named volume as uid/gid 10001 and mode 0400; Runtime and Control received only the file path and no raw-key environment variable |
| Runtime and Control health | pass live | Rebuilt/recreated Runtime and Control remained healthy with one Runtime worker; PostgreSQL, Redis, Gateway, and the preserved Console also remained healthy |
| Canonical execution and persistence | pass live, constrained | Authenticated deterministic echo completed through Console -> Gateway -> Control -> Runtime. A direct Gateway probe persisted matching tenant, idempotency, correlation, and trace evidence. Runtime fence state retained the same sanitized fingerprint across a normal stop/start and remained mode 0600 as uid 10001 |
| Fresh Console image build | blocked by network | The locked BuildKit build reused 658 of 659 cached packages, but npm registry metadata/attestation requests repeatedly returned `ECONNRESET`, `UND_ERR_SOCKET`, and curl error 23. The final attempt made no CPU or output progress for more than five minutes after about 24 minutes and was interrupted with exit 130 |
| Full Console propagation on current source image | blocked | The running Console image predates the forwarding repair. Source-level forwarding is covered, but a fresh image could not be produced, so end-to-end Console-originated idempotency/correlation propagation is not claimed |
| Resource guard | pass | Available memory remained about 4.1 GiB and disk availability about 33 GiB; builds were sequential and only one Runtime worker was active |

Earlier failed attempts are retained as negative evidence: an image command
initially omitted the required Compose project directory; a direct host bind
was unreadable by the non-root Runtime and was replaced by the least-privilege
staging volume; duplicate local administrator configuration caused an initial
401; and interrupted registry-bound Console builds exited 130. No weaker
unlocked/offline installation was substituted, supply-chain verification was
not disabled, and no volume was deleted.

The named Docker volume is an access-control mechanism, not encrypted secret
storage. Production operation still requires an external secret manager or
workload identity, rotation, and audited delivery. This gate does not establish
multi-worker scalability, distributed consensus, successful Linux isolation,
production readiness, or security certification.

## R6.14 Runtime execution-lease fencing — 2026-08-31

Branch: `Radin/capo-r6-validation`

Baseline: `2e1833534e2eae4093c5acb423aeb57a0fac7b1b`

Implementation commit: `edde9b019094d5dc521ac486a8467075ce8169b3`

This gate used the preserved single-worker `compose` Quickstart and canonical
PostgreSQL database. Builds and suites ran sequentially. No volume, persisted
record, credential, or security control was removed.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Pre-fix reproduction | reproduced | Before the change, a direct Runtime command without lease metadata executed with exit code 0, and backdating an active resource lease did not cause the next lifecycle heartbeat to reclaim it |
| Additive lease model | pass | `runtime_execution_leases` stores a monotonic generation, status, expiry, timestamps, and only the SHA-256 token hash; the raw token exists only in the bounded Control dispatch object and gRPC metadata |
| Targeted Control and lint | pass | `46 passed`; Ruff passed. PostgreSQL concurrency reported `1 passed`, and the complete Control suite reported `90 passed` with three existing deprecation warnings |
| Runtime regression | pass after environment workaround | The repository target directory was root-owned and Cargo failed on `.cargo-build-lock` with permission denied. Using isolated `CARGO_TARGET_DIR=/tmp/omerta-r614-target` produced `11 passed`; formatting passed and token-debug redaction was exercised |
| Architecture and Python regression | pass with exclusions | Architecture reported `72 passed, 1 deselected`; full Python reported `235 passed, 2 skipped, 1 deselected, 3 warnings`. The intentionally red Structure completion gate remained excluded |
| Compose render and sequential images | pass | Canonical render exited 0. Control built from cache; the locked cold Runtime release image built in 22 minutes 39 seconds. The two image builds did not overlap |
| Missing-lease rejection | pass live | After recreating Runtime then Control, a direct Runtime request without lease metadata returned gRPC `FAILED_PRECONDITION` instead of executing |
| Leased dispatch and generation fence | pass live | A real Control dispatcher call completed deterministic echo execution, released both leases, and restored zero active leases. A separately scheduled generation executed once; replaying identical metadata was fenced by Runtime |
| Expiry reclamation | pass live | A test execution lease was backdated without deleting it. The lifecycle heartbeat marked the attempt, resource lease, and execution lease `expired`, restored full declared CPU/RAM, and returned the worker to zero active leases |
| Schema, persistence, and log checks | pass | Migration check reported current schema; all ten persisted execution-lease tokens were valid 64-character hashes, with zero active resource/execution leases. Runtime logs contained no lease-token field |
| Quickstart smoke | pass | PostgreSQL, Redis, one Runtime, installer, Control, Gateway, and Console passed; Runtime registration was fresh and the Console -> Gateway -> Control health chain was healthy |
| Resource guard | pass | Available RAM was about 4.0 GiB before builds and 4.2 GiB after acceptance, above the 1 GiB stop threshold |

Failed validation attempts are retained. The first targeted Python run reported
`3 failed, 25 passed` because three expected-table/finish fixtures were stale;
the fixtures were updated and the affected suites passed. A one-line live probe
used invalid Python syntax and exited 1 before execution. The first live replay
probe proved the Runtime rejection but then called a keyword-only cleanup
argument positionally and exited 1; its single test lease was subsequently
finished without deletion, and the corrected independent probe passed. No
failed command was treated as evidence of success.

R6.14 establishes bounded stale-dispatch protection for the current
single-Control, single-Runtime prototype. The metadata token is not
cryptographically verified against Control storage and does not authenticate
the caller on the current unauthenticated internal gRPC transport. Runtime's
generation fence is in memory, resets on restart, and does not cancel work that
was already admitted. This gate is not evidence of durable post-restart
fencing, multi-Control coordination, distributed consensus, successful Linux
isolation, scalability, production readiness, or security certification.

## R6.13 atomic scheduler leases — 2026-08-31

Branch: `Radin/capo-r6-validation`

Baseline: `4163f1ce4b708c237f8b03d127e8f36753dc9e94`

Implementation commit: `076db60620cf8c1b43fee921a76e47acf9a2c99a`

This gate used the preserved single-worker `compose` Quickstart and canonical
PostgreSQL database. It did not run a benchmark, add a second Runtime, delete a
record or volume, or expose a credential.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Pre-fix concurrent reproduction | failed as expected | Two concurrent 600m CPU requests were both selected on a 1000m worker, availability remained 1000m/512 MB, three persisted attempts produced an `active_leases` value of 1, and a same-identity race raised `IntegrityError` instead of replaying |
| Atomic resource model | pass | Additive `runtime_resource_leases` rows persist CPU/RAM, acquisition and release state; no existing table, column, API, or record was removed |
| Targeted scheduler/migration tests | pass | `11 passed`; accounting, aggregate capacity, heartbeat preservation, idempotent release, audit rollback, and migration idempotency were exercised |
| PostgreSQL concurrency regression | pass | `1 passed`; concurrent same-identity calls produced one lease plus one replay, and only one of two concurrent 600m requests was admitted |
| Control regression | pass | `83 passed`, with three FastAPI/Starlette deprecation warnings |
| Architecture regression | pass | `72 passed, 1 deselected`; the intentionally red Structure completion gate remained excluded |
| Full Python regression | pass with skips | `228 passed, 2 skipped, 1 deselected, 3 warnings`; the two module-level skips are the formally retired legacy Agent Catalog and stream-service namespaces |
| Compose render and Control image build | pass | Canonical render exited 0; the Control image built sequentially and the active `compose-control-1` service became healthy after a no-dependency recreate |
| Live Control scheduling | pass | An authenticated Control request selected `runtime-quickstart-1`; finish returned the worker to 1000m CPU, 512 MB and zero active leases |
| Live heartbeat reconciliation | pass | A 250m/128 MB lease remained at 750m/384 MB after a real lifecycle heartbeat, then returned to full capacity after one idempotent finish |
| Resource guard | pass | Available RAM remained about 3.8 GiB after acceptance; one Runtime worker was used and builds/tests ran sequentially |

Two environment/operator failures are retained as negative evidence. The host
has no `python` alias (exit 127), and system `python3` has no pytest module; the
repository `.venv312` interpreter was therefore used. An initial Control
recreate omitted the active project name, targeted the stopped `omertaos`
project, recreated its stopped Control container, removed its unattached
`omerta-r5-net` network, and then failed because port 8000 belonged to the
preserved `compose` stack. No volume was removed. The corrected command used
`-p compose`, rebuilt only Control, and passed. The stopped
`omertaos-control-1` container remains created and was not broadly cleaned up.

R6.13 is evidence for bounded single-Control transaction correctness on the
canonical PostgreSQL backend. It is not evidence of Runtime-side lease fencing,
automatic reclamation after a Control crash, multi-Control serialization,
distributed consensus, scalability, production readiness, or security
certification.

## R6.12.2 trusted Gateway headers — 2026-08-31

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `db32030` (`fix(security): authenticate
trusted control headers`). Control now uses one constant-time Gateway service
token verifier for Configuration, Network, and Runtime administrative routes.
Gateway sends that token on Network reads before Control consumes forwarded
roles for admin versus enabled-only view filtering.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Targeted Control security tests | pass | `7 passed, 3 existing deprecation warnings`; covered forged admin/user roles, wrong and raw tokens, valid Bearer access, enabled-only user/public views, full admin view, mutations, and Runtime route regression |
| Gateway tests | pass after environment correction | The first invocation used the host Node version and Vitest stopped before collection because `node:util.styleText` was unavailable. Re-running with the bundled compatible Node reported `5 files passed, 10 tests passed` and verified that Network reads carry service authentication before role context |
| Gateway static gates | pass | Production TypeScript build and ESLint exited 0; no dependency or lockfile changed |
| Control regression | pass | `80 passed, 3 existing deprecation warnings` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `225 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Compose render and sequential builds | pass | Canonical `config --quiet` exited 0; Control and Gateway images built one at a time from locked cached dependencies |
| Limited recreate and smoke | pass | Only Control and Gateway were recreated with `--no-deps --wait`; PostgreSQL, Redis, Runtime, Console, and all volumes remained in place. The complete Quickstart smoke and Console -> Gateway -> Control health chain passed |
| Live negative authentication | pass | Role-only Configuration and Network requests returned HTTP 403, and a raw service token without the Bearer scheme returned HTTP 403 |
| Live positive authentication | pass | Bearer service-token Configuration access, Network enabled-only user filtering, Network admin view, and authenticated Gateway Configuration/Network paths returned HTTP 200. No token or proxy payload was printed |
| Resource guard and final state | pass | Available memory remained about 3.7 GiB, all six existing application/data containers were healthy, and no volume deletion or broad shutdown command was used |

This closes the reproduced role-header trust issue for the current
Configuration, Network, and Runtime administrative compatibility routes. It
does not establish mTLS, workload identity, network segmentation, independent
authorization review, production hardening, penetration testing, or security
certification.

## R6.12.1 Runtime boundary repairs — 2026-08-31

Branch: `Radin/capo-r6-validation`

Validated implementation commits: `78b02b1` (`fix(control): enforce runtime
tenant and admin boundaries`), `2637cb7` (`fix(control): reconcile runtime
lifecycle state`), and `b0181ee` (`fix(control): paginate runtime audit trails`).
Only the existing `compose` Control image was rebuilt, sequentially, and only
its container was normally recreated. PostgreSQL, Redis, Runtime, Gateway,
Console, containers, and persistent volumes were retained.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Independent defect reproduction | pass | In-memory Control execution reproduced role-header-only admin access, cross-tenant attempt replay, heartbeat lease reset, stale tenant/capacity configuration, and silent oldest-100 audit truncation before repair |
| Targeted repair suites | pass after one test correction | Auth/scheduler/dispatch reported `17 passed`; lifecycle/scheduler/routes reported `21 passed`; audit/routes reported `4 passed`. The first lifecycle run had `1 failed` because the new assertion assumed capability JSON order; structural set comparison replaced that stale assumption |
| Control regression | pass | `79 passed, 3 existing deprecation warnings` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `224 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Static and Compose validation | pass with pre-existing note | Targeted Ruff lint and format checks, `git diff --check`, and canonical Compose `config --quiet` exited 0. A broader format probe identified the untouched pre-existing `control/audit/models.py` formatting difference; no unrelated formatting was applied |
| Sequential Control build/recreate | pass | The Control image rebuilt from locked cached dependencies and only `compose-control-1` was recreated with `--no-deps --wait`; it returned healthy without restarting data or Runtime services |
| Quickstart smoke | pass | PostgreSQL, Redis, Runtime, installer, Control, Gateway, Console, automatic registration, binary healthcheck, dependencies, and Console -> Gateway -> Control health chain passed |
| Service-token boundary | pass in local prototype scope | A role-header-only Runtime admin request returned HTTP 403; the configured service token succeeded. No token value was printed or recorded |
| Tenant collision boundary | pass | A second tenant using the same task/attempt identity was rejected without a selected node or idempotent replay |
| Lifecycle reconciliation and lease preservation | pass | A fresh live heartbeat reconciled trusted tenant/capability/capacity values and preserved an active validation lease; normal attempt finish restored the baseline lease count |
| Audit pagination | pass | A live tenant-scoped trail queried with limit 1 returned explicit truncation and a cursor; the next cursor returned the remaining event |
| Resource guard and final state | pass | Available memory was about 3.7 GiB before and after validation. The six existing application/data containers remained healthy and no volume deletion command was used |

These repairs close the reproduced local prototype defects but do not establish
independent authorization review, concurrent scheduler correctness, lease
fencing, immutable audit integrity, production isolation, native systemd
acceptance, scalability, production readiness, or security certification.

## R6.12 durable Runtime audit trail — 2026-08-31

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `c5a9246` (`feat(control): persist runtime
audit trails`). The run reused the preserved `omertaos-r6-two` PostgreSQL,
MongoDB, and MinIO volumes but started the base Quickstart with one project
Runtime worker. The previous secondary container remained stopped and was not
removed. The independent pre-existing Runtime remained healthy, so no more
than two Runtime processes were active on the host.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Static validation | pass | `git diff --check`, Python compile, and targeted Ruff checks exited 0 |
| Targeted audit/migration/scheduler/dispatch/routes | pass after one regression repair | First run reported `17 passed, 1 failed`: same-process cache replay bypassed the scheduler, exposing a missing durable replay event and an incorrect test expectation. Cache replay/conflict events were added; final targeted run reported `19 passed, 3 existing warnings` |
| Transaction rollback | pass | Injected audit persistence failure rolled back the attempt, lease increment, and scheduling decision together |
| Control regression | pass | `77 passed, 3 existing deprecation warnings` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `222 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Additive schema | pass | Control startup created `runtime_audit_events` on the preserved PostgreSQL database; migration tests apply the schema twice and no existing table or row is removed |
| Control image build | pass | Only the affected Control image built, sequentially, with locked cached dependencies. Runtime, Gateway, and Console builds were skipped because their code/images were unchanged |
| Resource guard | pass | Available memory was 3.6 GiB before startup, 3.3 GiB during live checks, and 3.6 GiB after shutdown, above the 1 GiB stop threshold |
| Initial Quickstart smoke | pass | The base project passed PostgreSQL, Redis, Runtime, installer, Control, Gateway, Console, automatic registration, dependency, and canonical health-chain checks |
| Tenant rejection evidence | pass after acceptance-input correction | The first intended success used unregistered `tenant-r612` and correctly returned application `ERROR`; durable audit recorded `runtime.schedule/rejected` with `no eligible runtime node`. The persisted node allowlist was preserved rather than overwritten |
| Authenticated canonical task | pass | A unique `tenant-primary` request traversed Console -> Gateway -> Control -> one Runtime and returned status `OK` |
| Durable reconstruction | pass | Admin-authenticated retrieval returned exactly `runtime.schedule`, `runtime.dispatch.start`, and `runtime.dispatch.success`, with matching tenant/task/attempt/node/correlation/trace and retry count 0 |
| Access and data minimization | pass in prototype scope | A different tenant returned an empty event list, no admin credential returned HTTP 403, and the schema/API contained no message, payload, stdout, stderr, idempotency-key, credential, secret, or token field |
| Restart persistence | pass | The same three events remained queryable after normal PostgreSQL and Control container restarts |
| Final Quickstart smoke | pass | The complete read-only smoke probe passed again after the restarts |
| Final shutdown | pass | `docker compose stop` left zero test-project containers running and preserved all three project volumes; no volume deletion command was used. The pre-existing Runtime remained healthy |

The persistence adapter is owned by Control and leaves the shared telemetry
primitive transport-neutral. Scheduling state, decision, and schedule audit
event commit together; dispatch-start persistence is a fail-closed barrier
before Runtime execution; terminal attempt state and outcome audit commit
together. Stored reasons are controlled strings and task/result bodies are not
accepted by the audit schema.

This is prototype-level durable reconstruction, not an immutable security log.
No retention policy, cryptographic integrity chain, external exporter,
independent authorization review, production isolation, native systemd
acceptance, benchmark, scalability result, production readiness, or security
certification is claimed. No credential, cookie, token, secret, or task payload
was printed or recorded.

## R6.11 bounded two-worker Quickstart acceptance — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `cd43d8f` (`feat(deploy): add bounded
two-worker quickstart`). The opt-in Compose override used exactly two local
Runtime workers, one sequential Control lifecycle manager, host ports Console
`13100`, Gateway `18180`, loopback Control `18102`, and loopback primary Runtime
`55151` on the isolated `omerta-r6-two-net` network. The secondary Runtime had
no published host port. This run did not modify or delete existing volumes.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Targeted lifecycle/architecture tests | pass | `25 passed`; JSON list validation, duplicate rejection, sequential probing, dual registration, bounded count, image reuse, and secondary port isolation were covered |
| Control regression | pass | `74 passed, 3 existing deprecation warnings` |
| Native/Quickstart regression | pass | `70 passed` |
| Architecture regression | pass | `72 passed, 1 intentionally excluded Structure completion gate` |
| Full Python regression | pass | `219 passed, 2 skipped, 1 intentionally excluded Structure completion gate, 3 warnings` |
| Compose rendering | pass after command repair | The first render omitted `--env-file` and stopped on required bootstrap variables; the first build omitted `--project-directory .` and stopped on a nonexistent relative context. The corrected canonical render parsed two nodes, reused one Runtime image, exposed no secondary host port, and kept Control loopback-only |
| Sequential image builds | pass with one dependency repair | Control built first. Initial `up --no-build` stopped at create because the project-specific Gateway image was absent; Gateway then built separately and the unchanged stack started. Runtime and Console builds were skipped because their unchanged images were explicitly reused |
| Resource guard | pass | Available memory was 3.9 GiB before startup, 3.4 GiB during live checks, and 3.9 GiB after shutdown; exactly two Runtime workers were running during acceptance |
| Two-node lifecycle | pass | PostgreSQL recorded both trusted endpoints as `healthy` with fresh heartbeats, declared tenant/capability sets, and capacities 1000/512 and 2000/1024; lifecycle probes ran sequentially |
| Full Quickstart smoke | pass twice | Initial and final probes passed service/container health, installer exit, automatic registration, dependencies, and the Console-to-Gateway-to-Control chain; the secondary Runtime binary healthcheck also passed directly |
| Authenticated round-robin | pass | Two unique `tenant-shared` tasks traversed Console -> Gateway -> Control -> Runtime and completed on primary then secondary; audit rows recorded both eligible nodes and trace context |
| Tenant-aware eligibility | pass | `tenant-primary` completed only on primary and `tenant-secondary` only on secondary; audit rows recorded the other node rejected for `tenant` |
| Capability and capacity eligibility | pass | Admin-authenticated scheduler probes selected only secondary for `resource.allocate` and for 1500 CPU millis/800 MiB; primary rejection reasons were `capability` and `capacity` |
| Least-loaded scheduling | pass after test-fixture repair | The first probe left two acceptance leases on secondary and therefore did not create the intended load difference. Those attempts were finished without deletion; the independent rerun made both workers eligible and selected the lower-load secondary |
| Bounded failover | pass | Primary stopped immediately after a fresh heartbeat. Attempt `:0` selected primary and ended `transport_error`; retry `:1` rejected unreachable primary, selected secondary, and completed with retry count 1 of 1 |
| Automatic recovery | pass | Restarting primary restored a fresh healthy heartbeat without manual registration; two subsequent shared tasks completed primary then secondary |
| PostgreSQL restart persistence | pass | Four expected failover/recovery attempt rows remained after a normal PostgreSQL container restart |
| Final shutdown | pass with note | `docker compose stop` left no test-project service running and preserved all three project volumes. Qdrant exited 143 on SIGTERM; other running services exited 0. The pre-existing `compose-runtime-1` was restored healthy |

The node list remains trusted local Control configuration. Runtime receives no
administrator credential and cannot self-authorize tenant eligibility. The
manager enforces a configurable default limit of 2 and hard maximum of 32, and
probes configured workers sequentially on this constrained host.

This acceptance demonstrates bounded local multi-node scheduling and one
worker failover for the allowlisted deterministic echo path. It does not
measure throughput or recovery-time performance and does not establish
scalability, distributed membership, consensus, leader election, lease
fencing, federation, successful Linux isolation, native systemd operation,
production readiness, or security certification. No credential, cookie,
token, or secret value was printed or recorded.

## R6.10 automatic local Runtime lifecycle — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated implementation commit: `ac39d51` (`feat(deploy): automate
quickstart runtime lifecycle`). The run recreated the isolated Quickstart
containers while preserving the existing volumes, used one Runtime worker, and
used host ports Console `13000`, Gateway `18080`, loopback Control `18002`, and
loopback Runtime `55051` on `omerta-r6-fixed-net`. No manual node registration
or heartbeat command was used.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Lifecycle and probe tests | pass | `tests/control/test_runtime_lifecycle.py` reported `6 passed`; coverage includes bounded opt-in configuration, Runtime `QueryMetrics` readiness, invalid JSON rejection, registration, unreachable refusal, and preservation of operator draining |
| Control regression | pass | `70 passed, 3 existing deprecation warnings` |
| Native/Quickstart regression | pass | `70 passed` |
| Architecture regression | pass | `71 passed, 1 intentionally excluded completion gate` |
| Full Python regression | pass | `214 passed, 2 skipped, 1 intentionally excluded completion gate, 3 warnings` |
| Compose rendering | pass | The rendered model selected loopback-only Control publishing and enabled the bounded 10-second local lifecycle interval; no rendered secret values were recorded |
| Control image build | pass | The affected image rebuilt sequentially with locked cached dependencies and exit 0. Runtime, Gateway, and Console images were unchanged and deliberately not rebuilt |
| Resource guard | pass | Available memory was 2.9 GiB before build, 3.4 GiB during final live checks, and 3.8 GiB after shutdown; it remained above the 1 GiB stop threshold |
| Automatic registration | pass | After container recreation, PostgreSQL contained `runtime-quickstart-1` at `runtime:50051`, state `healthy`, capability `terminal.execute`, declared capacity 1000 CPU millis/512 MiB, and a heartbeat newer than 30 seconds |
| Control host-port repair | pass on this host | Publishing Control as `127.0.0.1:18002:8000` returned a valid healthy payload. This removes unnecessary non-loopback exposure and eliminated the reset reproduced with the prior all-interface mapping |
| Full Quickstart smoke | pass twice | Both the initial and post-recovery probes passed container health, installer exit, Runtime binary health, fresh automatic registration, Control/Gateway/Console payloads, dependencies, and the Console-to-Gateway-to-Control health chain |
| Canonical task without manual heartbeat | pass | An authenticated Console API request traversed Gateway, Control, and Runtime and returned HTTP 200, status `OK`, and an exact deterministic echo |
| Runtime outage detection | pass fail-closed | Runtime alone was stopped. After the 30-second freshness threshold, the next authenticated canonical task returned application status `ERROR` with `RUNTIME_NODE_UNAVAILABLE`; PostgreSQL recorded the node `unreachable` with a stale heartbeat |
| Automatic recovery | pass | Starting the same Runtime container caused the Control supervisor to restore a fresh `healthy` heartbeat without a registration call. A new authenticated canonical task returned `OK`, followed by a second complete smoke pass |
| Final shutdown | pass with note | `docker compose stop` exited 0, no project containers remained running, all three project volumes were preserved, and no volume-deletion command was used |

The supervisor is enabled by the Quickstart Compose profile and remains opt-in
for other Control deployments. It probes the configured Runtime gRPC API before
registering or heartbeating, never gives Runtime an administrator credential,
does not let Runtime choose tenant eligibility, refuses to heartbeat a persisted
node whose endpoint differs from trusted Control configuration, and preserves
operator draining. Declared capacity is static local configuration rather than
measured host utilization.

This stage does not demonstrate browser UI interaction, multiple workers,
distributed membership, consensus, leader election, lease fencing, precise
recovery-time performance, native systemd operation, successful Linux
isolation, production readiness, or security certification. Two Python tests
remain skipped by their existing contracts, and the intentional Structure
completion gate was not run. No credential, cookie, token, task payload, or
secret value was printed or recorded.

## R6.9 authenticated canonical execution — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated repair commit: `cc52204` (`fix(runtime): propagate canonical dispatch
context`). Control, Gateway, and Console images were built sequentially from
that commit. The preserved isolated project used one Runtime worker, host ports
Console `13000`, Gateway `18080`, Control `18001`, and Runtime `55051`, plus the
`omerta-r6-fixed-net` network. The Control port was changed from `18000` while
diagnosing a host publishing failure; both ports exhibited the same reset.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Context regression tests | pass | Console allowlist `2 passed`; Gateway `4 files, 9 tests passed`; targeted Control transport `7 passed`; Runtime dispatch/transport `14 passed`. Three existing Python deprecation warnings remained |
| Architecture regression | pass after stale-reference repair | The first run reported `69 passed, 1 failed, 1 deselected` because README omitted three current canonical design links. Commit `168840d` restored the references; the targeted test passed and the full rerun reported `70 passed, 1 deselected`. The intentionally red completion gate remained excluded |
| Broader Console regression | pass | `10 files, 22 tests passed` after restoring the locked pnpm `11.13.1` installation; Prisma generation and the direct Next production build exited 0 |
| Service builds | pass | Gateway and direct Console production builds passed; Control, Gateway, and Console container images then built sequentially with exit 0. The unchanged Runtime image was not rebuilt |
| Compose rendering | pass | The isolated Quickstart configuration rendered with the selected images, network, and host ports; this was treated only as static configuration evidence |
| Resource guard | pass | Available memory was 4.0 GiB before startup, 2.8 GiB during final live checks, and 3.0 GiB after shutdown, above the 1 GiB stop threshold |
| Runtime registration and heartbeat | pass, manual | `runtime-r6-1` registered inside the Control network with tenant `tenant-r6` and the single `terminal.execute` capability; a fresh heartbeat reported `healthy` |
| Authenticated canonical task | pass in constrained scope | A real NextAuth session submitted `runtime.echo.v1` through Console `/api/proxy/tasks`; Console, Gateway, Control gRPC, and one Runtime completed it with HTTP 200, application status `OK`, and an exact deterministic echo |
| Tenant and context propagation | pass | PostgreSQL recorded tenant `tenant-r6`, the submitted idempotency key, selected node `runtime-r6-1`, status `completed`, and the submitted W3C traceparent. Runtime audit recorded matching task, tenant, agent, correlation/request, trace, and `authorized`/`completed` outcomes without logging the payload |
| Same-request replay | pass in constrained scope | Repeating the authenticated request with the same idempotency key returned the same task id; PostgreSQL retained exactly one task attempt |
| Service and dependency health | pass internally | Console and Gateway host health returned valid healthy payloads; Gateway reported Redis and Control healthy; Console's system endpoint reported the Console-to-Gateway-to-Control chain healthy; Control's internal HTTP health passed |
| Quickstart smoke | partial failure | PostgreSQL, Redis, Runtime, installer, Control, Gateway, and Console container checks plus Runtime binary health passed. The next host probe failed with exit 1 because Docker's published Control port returned an empty/reset response even after isolated port change and Control recreation; internal and Gateway-to-Control probes remained HTTP 200 |
| Final shutdown | pass with note | `docker compose stop` exited 0, all services stopped, all three project volumes were preserved, and no volume-deletion command was used. Qdrant exited 143 after SIGTERM; the other running services exited 0 |

Failed toolchain attempts were not substituted silently: system Node 18 was
incompatible with the current JavaScript gates; an initial pnpm invocation
could not confirm a module purge without a TTY; the resulting partial module
state lacked Rollup's optional binary; and the pnpm build wrapper's dependency
status/network activity was interrupted with exit 130. The exact locked Console
dependencies were restored without lockfile changes, and the direct underlying
test and build commands subsequently passed. A host `python` invocation also
failed with exit 127 before acceptance orchestration began; the available
`python3` executable ran the unchanged probe successfully. Two diagnostic shell
pipelines produced misleading zero statuses after `curl` failures; neither was
accepted as evidence, and strict independent probes reproduced the failure.

This stage demonstrates one authenticated API request through the complete
canonical service path on one local worker. It does not demonstrate a browser
UI click flow, automatic Runtime registration/heartbeat, multiple workers,
scalability, successful Linux isolation, durable Control audit export,
production readiness, or security certification. The published Control host
port remains an unresolved environment/deployment gate. No credential, cookie,
token, echoed payload, or secret value was printed or recorded.

## R6.8 isolated Quickstart smoke — 2026-08-30

Branch: `Radin/capo-r6-validation`

Validated smoke repair commit:
`0c53328` (`fix(deploy): target isolated quickstart smoke`). The live run reused
the preserved single-worker `omertaos-r6-fixed` containers and images from the
R6.7 acceptance; no image build or dependency installation was performed. This
therefore validates the repaired read-only smoke probe and preserved stack, not
a fresh image build of the current branch.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Failure reproduction | pass | The previous script rejected `--project-name` with exit 1, so it could not target the isolated acceptance project explicitly |
| Smoke contract regression | pass | `6 passed`; includes mocked project selection, isolated ports, Runtime healthcheck, installer lookup, and invalid-port rejection |
| Native contract regression | pass | `70 passed` |
| Deployment architecture regression | pass | `14 passed, 57 deselected` for the focused Quickstart/deployment/CAPO selection |
| Static validation | pass | Bash syntax, Ruff, `git diff --check`, and sanitized Compose `config --quiet` exited 0 |
| Resource guard | pass | Available memory was 2.2 GiB before startup and 1.9 GiB during live smoke, above the 1 GiB stop threshold |
| Positive isolated smoke | pass | The selected project reported healthy PostgreSQL, Redis, Runtime, Control, Gateway, and Console containers; installer exit 0; Runtime binary health; service payloads; Gateway dependencies; and the Console-to-Gateway-to-Control health chain |
| Wrong-project negative probe | pass | A nonexistent project failed with exit 1 at the missing PostgreSQL container even though the independent default-port `compose-*` stack remained healthy |
| Final shutdown | pass with note | Compose stop exited 0, persistent volumes remained present, Qdrant exited 143 after SIGTERM, and the other R6 containers exited 0 |

The smoke probe remains read-only and does not start, restart, migrate,
bootstrap, or stop services. This stage does not submit a task through Console,
prove the Console-to-Runtime execution path, validate multiple workers, or
change the existing isolation and production-readiness evidence boundaries. No
credential value was printed or recorded.

## R6 Quickstart restart persistence — 2026-08-29

Branch: `codex/capo-r5-runtime-execution`

Validated commit: `5858d3696ad30a6709b60180d2690b13baf1621b`.
The run used one Runtime worker and the preserved `omertaos-r6-fixed` volumes.
It did not build images, run benchmarks, or modify the concurrently running
`compose-*` stack. The isolated acceptance ports were Console `13000`, Gateway
`18080`, Control `18000`, and Runtime `55051`; the Docker network was
`omerta-r6-fixed-net`.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Resource guard | pass | Available memory was 2.0 GiB before startup, 1.8 GiB at initial health, and 1.7 GiB after restart; it remained above the 1 GiB stop threshold |
| Quickstart startup | pass after two operator-configuration failures | An initial resumed command omitted the isolated network and encountered stale container network metadata; after recreation, the default Runtime port was occupied by the preserved `compose-*` stack. Reapplying the isolated network and port settings started the unchanged images successfully |
| Service health | pass | Console, Gateway, Control, Runtime, PostgreSQL, and Redis were healthy after startup and again after a complete normal stop/start cycle |
| Installer idempotency | pass | The one-shot install container exited 0 on both starts; the user-row count remained `1` |
| Prisma migration persistence | pass | Migration count remained `2`; the sanitized migration-name fingerprint remained `e2e79dd0d4a8b0bed0724ce827291103` before and after restart |
| Volume persistence | pass | PostgreSQL, MongoDB, and MinIO volumes remained present after the final `docker compose stop` |
| Final shutdown | pass with note | Compose stop exited 0; Qdrant exited 143 after SIGTERM and the other containers exited 0; no volume deletion command was used |

The failed startup attempts are environment/configuration evidence, not service
acceptance. This gate establishes restart persistence and idempotent bootstrap
for the constrained single-worker Quickstart only. It does not establish
multi-worker scalability, Linux isolation, native systemd acceptance,
production readiness, or security certification. No credential value was
printed or recorded.

## R5 constrained Runtime acceptance — 2026-08-28

Branch: `codex/capo-r5-runtime-execution`

Validated deployment/configuration commit:
`0deccc85d6ba5601fb181ce9968b6bdd23e40014`. The Runtime dispatch source is in
`711395a` and `681ff8f`; the build-context checkpoint is `d4ff77a`. Nothing in
this acceptance run was pushed or merged.

The run used one Runtime worker on the recorded 8 GB Linux host. Available
memory remained above 3 GB, services and image builds were executed
sequentially, and the existing `compose-*` stack was preserved. The R5 stack
used separate host ports and the `omerta-r5-net` network.

| Gate | Result | Executable evidence and boundary |
|---|---|---|
| Architecture regression | pass | `68 passed, 1 deselected`; the intentionally red completion gate was excluded |
| Full Python regression | pass | `203 passed, 2 skipped, 3 warnings` before live acceptance |
| Runtime image build | pass | Locked release build completed in 17 minutes; cold-build duration is not a performance benchmark |
| Runtime image identity | pass | Image ran as `runtime`; one worker became healthy on loopback port `55051` |
| Control image build | pass after transient network failure | Initial Python base-layer request returned HTTP 403; an independent pull succeeded and the unchanged rebuild passed |
| Gateway image build | blocked | First `npm ci` attempt timed out fetching locked `yargs-parser@21.1.1`; a direct URL probe later returned HTTP 200; the second attempt made no progress for 15 minutes and was stopped with exit 130 |
| Console image/live service | skipped | Gateway image gate blocked the canonical full-stack sequence; no weaker substitute was used |
| Backend startup | partial pass | PostgreSQL, Redis, one Runtime, and Control were healthy; Qdrant and MinIO were running but have no explicit Compose readiness probe |
| Control health | pass | `/health` and `/v1/health` returned `{"status":"ok","service":"control"}` on isolated host port `18000` |
| Node registration and heartbeat | pass | `runtime-r5-1` registered with `terminal.execute`, tenant `tenant-r5`, then accepted a heartbeat |
| Worker failure detection | pass in constrained scope | A heartbeat older than the 30-second threshold changed the node to `unreachable` and dispatch failed closed with `RUNTIME_NODE_UNAVAILABLE` |
| Allowlisted execution | pass | Fresh heartbeat plus gRPC Submit selected `runtime-r5-1`; `runtime.echo.v1` returned exit code 0 and `r5-audit-ok\n` |
| Context/audit propagation | pass at Runtime log boundary | Tenant, task, attempt, request, trace, actor, and authorized/completed outcomes were logged; the echoed payload was not logged |
| In-process idempotency | pass | Identical replay returned `idempotent_replay=true`; Runtime audit-event count did not increase |
| Post-restart idempotency | pass fail-closed | After normal Control restart, replay returned `RUNTIME_RESULT_REPLAY_UNAVAILABLE`; Runtime did not execute it again |
| PostgreSQL persistence | pass | A non-sensitive probe row remained readable after normal PostgreSQL restart |
| Shutdown and volume preservation | pass with note | `docker compose stop` preserved `omertaos_postgres-data` and `omertaos_minio-data`; Qdrant reported exit 143 after SIGTERM while the other R5 services exited 0 |
| Full canonical request path | blocked | Current Gateway image was unavailable, so Console -> Gateway -> Control -> Runtime was not claimed |

Runtime audit evidence required an acceptance-only Compose override setting
`RUST_LOG=info`; the host exports `RUST_LOG=warn`. Control's `emit_audit`
primitive still returns only an in-memory entry and has no durable exporter.
Successful `lite`-profile command execution is not evidence of completed Linux
namespace/seccomp isolation, production readiness, security certification, or
multi-worker scalability.

## R3 current reconciliation — 2026-08-10

Official branch `CAPO` is synchronized at evidence commit
`91921367cdfa600abb91710f7d699a183af800fa`. The current lockfiles are tracked:

| Lockfile | SHA-256 |
|---|---|
| `runtime-daemon/Cargo.lock` | `9C7EBC387FEF54CB7C2BBC70F96EA2DDF690F7636D18175FA251B96D5D5433F6` |
| `gateway/package-lock.json` | `CECAD9E18FB37754EBDF9CAC078BDC0A10CFE939365651CEB84160746866D55F` |
| `console/pnpm-lock.yaml` | `98FCA5264683D58F5274C14A62971FE56679AC7AD0C3A61C49722CFB0D4555B1` |

CI run [`31358631289`](https://github.com/Hamedghz/OMERTAOS/actions/runs/31358631289)
passed architecture, lint, all service builds, Python and locked Cargo tests,
the locked Runtime release build, integration, security, seven image builds and
six architecture-independent checks. The remaining emulated arm64 Console image
job stayed in progress for more than three hours. R3 moves arm64 image builds to
the native `ubuntu-24.04-arm` runner and retains the locked Linux Runtime binary
plus its SHA-256 as a CI artifact.

Current Gate status:

| Gate | Status | Current evidence |
|---|---|---|
| S2 Core Migration | passed | Four service builds plus locked Runtime test/release build |
| S3 Supporting Migration | passed | 63 architecture tests and deterministic retired-root guards |
| S5 Legacy Retirement | passed (repository scope) | Explicit approval, absent retired roots, no executable dependencies |
| S6 Architecture Validation | passed | Full Python and architecture suites plus CI boundaries |
| Gate R | pending | Requires the R3 commit to be clean, pushed, fully green and architecture-complete |
| Native live acceptance | pending | No current Ubuntu/systemd reboot/smoke/update/rollback/restore evidence |
| Docker live acceptance | pending | Image build is not running-stack smoke/parity evidence |

The historical report below remains immutable evidence of its original review.

> Historical snapshot: this report records the 2026-07-12 CAPO review. The
> current Native N1-N8 contract supersedes its missing-lockfile and stop/disable
> rollback descriptions. Gateway and Runtime lockfiles now exist; N8 uses
> immutable releases, canonical backup verification, and atomic code rollback.
> Live Linux/systemd, Runtime build, smoke, update, and restore acceptance remain
> pending until rerun and recorded on the intended host.

Date: 2026-07-12 (Asia/Tehran)

Branch: `capo`

Baseline: `b4021a4327d63b8db0c0e0f87267dec28907cb36`

Phase 6 head reviewed: `d4e96723b5b6341af5c3b4c899d9fdaca2054331`

## Decision

The seven-phase CAPO implementation is **conditionally accepted for human
review and Linux-host validation**. Static contracts, configuration rendering,
application entrypoint checks, Gateway/Console builds, and the verified recovery
baseline pass. Production use, permanent legacy-path retirement, merge, and
deployment are not accepted by this report.

Native systemd acceptance remains pending on the intended Debian/Ubuntu SSD
host. Running Docker Quickstart acceptance also remains pending because the
local Docker daemon did not respond during Phases 6 and 7. These two gates are
independent and neither may be inferred from static validation.

## Delivered scope

- Verified external Git/source backup and reconstruction map.
- Non-secret CAPO environment and idempotency/security contract.
- Debian/Ubuntu, PostgreSQL, and Redis installers with dry-run behavior.
- Canonical Control, Gateway, Console, and Runtime build/install scripts.
- Four non-root systemd services, aggregate target, and lifecycle scripts.
- Read-only Native/Quickstart smoke checks, contract tests, troubleshooting,
  canonical backup verification, and immutable release rollback.

Across Phases 1–6, CAPO added 29 tracked files with 1,529 lines relative to the
baseline. No existing source, schema, table, data, legacy path, or public API was
removed or moved.

## Evidence

| Check | Result | Notes |
|---|---|---|
| Backup SHA-256 and Git bundle | pass | Three hashes match; bundle reports complete history |
| CAPO Bash syntax and `--help` | pass | All reviewed scripts via Git Bash |
| CAPO PowerShell contracts | pass | Ports, env, systemd hardening, rollback, forbidden commands |
| Quickstart/Local Compose rendering | pass | Both `config --quiet` checks |
| Architecture tests | pass | `14 passed in 0.95s` in final review |
| Control import | pass | `control.app.main:app` |
| Gateway TypeScript build | pass | `tsc -p tsconfig.json` |
| Console production build | pass with warnings | Missing local Prisma generation/DB URL; stale browser data |
| Runtime metadata | pass | Cargo manifest resolves without dependency download |
| Runtime release build | blocked | `index.crates.io:443` unavailable after retries |
| Full Python regression | blocked by legacy collection | 11 import errors for removed `os.control`, `os.kernel`, `aion`, and CLI paths |
| Native Linux smoke | pending | Requires intended Linux SSD/systemd host |
| Running Quickstart smoke | pending | Docker daemon did not respond; stack was not mutated |

No coverage report was generated because CAPO changes deployment assets and
documentation rather than application runtime code.

## Security and data review

- Services run as the dedicated non-login `omertaos` account and include
  `NoNewPrivileges` and `PrivateTmp`.
- Real secrets remain outside Git in `/etc/omertaos/omertaos.env`.
- PostgreSQL and Redis are required; optional stores default disabled.
- Static scanning found no executable destructive disk, Git move/removal,
  `DROP`, or `TRUNCATE` command in CAPO assets.
- Rollback preserves source, configuration, accounts, databases, volumes, and
  persistent state.

## Open acceptance gates

1. Run installers twice on a disposable Debian/Ubuntu SSD host and confirm the
   second execution is idempotent.
2. Run `first-boot.sh --version VERSION --backup PATH --start`, Native smoke,
   journald review, reboot recovery, stop/start, update, and rollback
   preview/execute with an operator present.
3. Start Quickstart, run its smoke test, verify Console → Gateway → Control →
   Runtime, and stop it without deleting volumes.
4. Restore the external backup in an isolated environment and reconcile the
   resulting commit and data checks.
5. Resolve or formally quarantine the legacy Python tests before treating the
   repository-wide regression suite as green.

Until all relevant gates pass, the permanent-deletion gate stays closed and
human review is required before merge or any production use.
