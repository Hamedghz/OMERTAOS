# ADR 0001: Canonical AION service ownership

> Naming clarification: ADR 0002 defines `OMERTA_*` as the canonical product
> configuration namespace. The AION wording in this historical ownership ADR
> identifies the source branch of the consolidation and does not define a
> runtime configuration or product namespace.

- Status: accepted
- Date: 2026-07-05
- Contract frozen: 2026-07-12 (Structure S1)

## Context

The repository contains competing generations: `control/` and `control-plane/`,
`runtime-daemon/` and `rust-runtime/`, `data/`, `database/` and `db/`, plus model,
schema and deployment duplicates. Earlier documentation also disagrees about which
generation is primary. A previous cleanup removed the former `control.os`
implementation while leaving its callers and wrappers behind.

## Decision

The canonical execution chain is `console -> gateway -> control -> runtime-daemon`.
Canonical supporting owners are `data/`, `registry/`, `policies/`, `schemas/`,
`shared/`, `deploy/`, and `integrations/`. Legacy roots are migration inputs and
compatibility surfaces only. New feature behavior must not be added to them.

The Python "kernel" is not restored as a privileged executor. Its useful tenant,
scheduling and governance concepts move into Control; all host side effects stay in
the Rust Runtime Daemon.

This chain is exclusive, not illustrative. Console may call only Gateway public
interfaces. Gateway may call Control but may not import domain persistence
adapters or query application databases. Its narrowly scoped Redis use for
rate-limiting, idempotency and ephemeral coordination is infrastructure state,
not a domain-data exception. Control may reach host processes only by a
versioned Runtime client; direct subprocess, shell, syscall and sandbox behavior
in Python is forbidden.

Canonical contract sources live under `schemas/v1/`. Generated Python,
TypeScript and Rust clients live under `shared/generated/` and must not be
hand-edited. Deployment assets have one owner, `deploy/`; root wrappers may only
delegate to that owner.

## Consequences

- Deleted capabilities are recovered selectively into canonical modules.
- Existing public APIs remain stable through Gateway adapters during migration.
- Compatibility imports point toward canonical code.
- Cleanup is delayed until callers and deployment references are zero.
- CI architecture tests must inspect canonical paths, not legacy ones.
- New source imports from `control-plane`, `rust-runtime`, `database`, or `db`
  are rejected immediately.
- A blocking migration gate remains red while legacy roots or bypass paths
  exist; it becomes green only after their staged migration and validation.
- Historical mentions under ADR and migration documents are evidence, not
  executable dependencies.

## Rollback

This is a documentation and ownership decision. Reverting it requires a new ADR,
an explicit service migration plan, compatibility tests and human approval; it must
not be reversed by moving individual files ad hoc.
