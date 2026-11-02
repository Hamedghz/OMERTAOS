# Evidence and claims

**Document role:** current claim ledger for academic and technical review.

## Evidence levels

| Level | Definition |
|---|---|
| **E1 — repository-verified** | The claim is checked by an executable repository test or deterministic static gate. |
| **E2 — implemented prototype** | Relevant source and targeted checks exist, but the complete deployment or acceptance path has not been demonstrated. |
| **E3 — design target** | The repository documents the behavior, but implementation or empirical validation is incomplete. |
| **E0 — unsupported** | No adequate evidence is present; the statement must not be presented as a result. |

## Claim ledger

| Claim | Level | Repository evidence | Boundary of the claim |
|---|---|---|---|
| The canonical request path is Console -> Gateway -> Control -> Runtime. | E1 | `tests/architecture/test_layer_boundaries.py`, `test_canonical_contract.py`, `STRUCTURE.md` | Proves repository dependencies and selected routes, not network segmentation in a deployed cluster. |
| Canonical top-level ownership replaced migration-era duplicate roots. | E1 | `tests/architecture/test_target_structure.py`, Structure S6 report | Applies to the evaluated tree/commit; historical material remains under migration evidence. |
| Control does not directly execute host subprocesses. | E1 | `tests/architecture/test_subprocess_boundaries.py` | Static and targeted source scope; not a formal whole-program proof. |
| Runtime denies execution when required sandbox backends are unavailable. | E2 | `runtime-daemon/src/sandbox/*.rs`, `runtime-daemon/tests/migration_contract.rs` | Demonstrates fail-closed stubs; it does not demonstrate successful isolated execution. |
| Runtime checks named capabilities before selected RPC operations. | E2 | `runtime-daemon/src/security/capability.rs`, `server.rs` | Current signature validation is minimal and does not establish a production cryptographic grant protocol. |
| Gateway and Control form separate transport/orchestration services with an authenticated local HTTP service boundary for current administrative compatibility routes. | E2 | R6.12.2 commit `db32030`; `gateway/src/routes/config.ts`, `gateway/src/routes/network.ts`, `control/app/service_auth.py`; Gateway/Control tests and constrained live acceptance | Configuration, Network, and Runtime admin routes reject role-only headers and require the configured Gateway service token; Network roles affect view filtering only after service authentication. This is a shared-secret local prototype boundary, not mTLS, workload identity, network segmentation, independent authorization review, or production certification. |
| Control contains a minimal Runtime node registry, local lifecycle supervisor, and scheduler prototype. | E2 | `control/scheduling/`, `control/app/runtime_nodes/`, commits `076db60`, `edde9b0`, `1d9183b`, scheduler/lifecycle/PostgreSQL concurrency tests, R5 through R6.15 and P3 constrained acceptance; recovery harness `9769808` | Demonstrates single-Control registration, bounded sequential probe-driven heartbeat for two local workers, stale-worker detection, automatic local recovery, tenant/capability/capacity eligibility, round-robin/least-loaded selection, bounded retry, tenant-scoped attempt replay, trusted-config reconciliation, PostgreSQL-serialized attempt identity, atomic worker-capacity reservation/release, bounded execution-lease expiry, and lifecycle-driven capacity reclamation. With persistent fence state configured, one constrained live Runtime rejected identical, still-unexpired signed metadata before and after normal Runtime restart; the exact generation/expiry record remained unchanged. Declared capacity remains static local configuration. The lease token is not caller authentication. This does not prove cancellation of admitted work, fencing after lost/corrupt state or independent restore, multi-Control consistency, distributed membership, consensus, leader failover, or multi-worker scalability. |
| Control persists a tenant-scoped Runtime scheduling and dispatch trail. | E2 | R6.12 commit `c5a9246`; R6.12.1 commits `78b02b1` and `b0181ee`; `control/audit/`; Control audit/migration/dispatch tests; `docs/capo/acceptance-report.md` | A constrained live task produced durable schedule/start/success events with actor, task, attempt, node, correlation, trace, outcome, and retry metadata; tenant mismatch returned no events, a role-only request returned 403, and configured service-token access succeeded. Bounded cursor pagination was exercised across two pages, and earlier events survived PostgreSQL and Control restarts. The table is not cryptographically tamper-evident, independently exported, retention-managed, or evidence of production authorization. |
| The allowlisted `runtime.echo.v1` path can execute through the authenticated canonical service path on one or two constrained local Runtime workers. | E2 | R5 commits `711395a`, `681ff8f`; R6.9 commit `cc52204`; R6.10 commit `ac39d51`; R6.11 commit `cd43d8f`; R6.12 commit `c5a9246`; `docs/capo/acceptance-report.md` | Constrained live runs demonstrated authenticated Console API -> Gateway -> Control -> Runtime traversal, tenant/correlation/trace/idempotency propagation, same-request replay, durable tenant-scoped Control audit for one successful task, local two-worker round-robin and tenant eligibility, one bounded failover retry, probe-driven recovery, and fail-closed post-restart replay. Browser UI traversal, independent audit export, production isolation, broader commands, and scalability remain unproven. |
| Selected Quickstart application settings support canonical OMERTA and documented legacy AION process environments. | E2 | M4.1.3 constrained acceptance; `scripts/validate_quickstart_environment_parity.py`; harness commit `d02a54b`, audit-correlation repair `9689b8a`; `docs/capo/acceptance-report.md` | Two sequential one-Runtime runs covered 52 configured service/key instances (44 canonical names), real Console login, Runtime echo/replay and matching tenant/correlation/trace on all three new audit events. Legacy warnings showed 28 distinct aliases consumed; not every configured setting was behaviorally exercised. Conflict preflight rejected 45 pairs; only the Runtime bind conflict was separately tested against an actual binary. Canonical-only lease secrets remain canonical. This is not exhaustive compatibility, fresh-install/upgrade restore acceptance, distributed scalability, or production security evidence. |
| A constrained Quickstart fresh installation and existing-data reapply preserve selected state across normal container restarts. | E2 | P3 partial acceptance, `scripts/validate_quickstart_recovery.py`, tests and harness `9769808`, `docs/capo/acceptance-report.md` | Sequential one-Runtime runs on new and existing test volumes preserved administrator identity, migration checksums, original task audit IDs, MongoDB fixture, MinIO object and Qdrant payload. Canonical authenticated echo worked after restart; Gateway replayed from Redis while a separate Control gRPC replay failed closed without another dispatch. This is not durable Control result recovery, named-volume Redis queue recovery, encrypted backup/independent restore, historical upgrade compatibility, power-loss testing or production recovery acceptance. Backup/restore and upgrade on an older-data clone remain blocked. |
| The system provides complete Linux namespace, mount, seccomp, and process isolation. | E0 | Backends currently return errors | Must not be claimed until implementation and negative/escape testing pass on a compatible Linux host. |
| OMERTAOS provides distributed membership, scheduling, and federation. | E0 | Cluster documents plus minimal node-registration/resource-report stubs | These are design topics, not a working distributed subsystem. |
| OMERTAOS has measured scalability or lower latency than alternatives. | E0 | Benchmark blueprint only | No controlled quantitative results are committed. |
| OMERTAOS is security-certified, formally verified, or penetration-tested. | E0 | No certification or independent report | Architecture and CI scans are not certification. |
| Native Linux/systemd and running Quickstart paths have passed production acceptance. | E0 | CAPO acceptance report records pending gates | Static checks and Compose rendering are insufficient. |

## Acceptable wording

Use:

- “the architecture tests reject selected bypass paths”;
- “the Runtime prototype currently fails closed when isolation backends are
  unavailable”;
- “the repository defines a benchmark protocol”;
- “one constrained local worker executed the allowlisted Runtime echo path”;
- “a constrained local Runtime task produced a durable tenant-scoped Control
  audit trail.”

Do not use without new evidence:

- “provably secure”;
- “production-ready”;
- “fully isolated”;
- “horizontally scalable”;
- “low latency” or “high throughput”;
- “validated in real-world deployments.”

## Evidence provenance

Results should record:

- repository URL and exact commit SHA;
- branch only as navigation context, not as a stable identifier;
- operating system, architecture, toolchain, and dependency lock state;
- exact command and exit code;
- test counts, skipped tests, warnings, and unavailable external services;
- generated logs or reports with secrets removed.

The dated migration and CAPO reports are useful provenance but may become stale.
Current reviewers should rerun the commands in
[Reproducibility](reproducibility.md).
