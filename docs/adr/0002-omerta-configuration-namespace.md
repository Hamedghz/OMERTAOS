# ADR 0002: Canonical OMERTA configuration namespace

- Status: accepted
- Date: 2026-08-31
- Scope: configuration names and protocol-domain identifiers

## Context

OMERTA is the stable product identity. AION, CAPO and WARLOCK identify branches,
editions or integration targets; they are not stable product namespaces. The
repository nevertheless accumulated `AION_*` environment variables across
Runtime, Control, Gateway, Console, deployment assets and tests. It also contains
a smaller `OMERTAOS_*` installer namespace and standard third-party variables.

Allowing a branch or edition name to own infrastructure configuration makes the
same service contract appear product-specific, complicates cross-branch merges
and encourages each edition to create incompatible operator settings.

## Decision

New product-owned environment variables and protocol-domain identifiers use the
`OMERTA_*` prefix. Branch and edition names must not be used as configuration
prefixes. If runtime edition selection becomes necessary, it is represented by
an explicit value such as `OMERTA_EDITION=AION`, not by a new variable family.

Existing `AION_*` variables migrate in bounded vertical slices:

1. The canonical `OMERTA_*` name is read first.
2. A legacy alias may be read only where an already-deployed contract requires a
   compatibility window.
3. If canonical and legacy values are both present and differ, startup or the
   affected operation fails closed without logging either value.
4. Deprecation diagnostics may name variables but must never print secret values.
5. Alias removal requires executable acceptance evidence and explicit approval.

The R6.15 execution-lease HMAC setting was introduced but not provisioned or
deployed before this decision. It therefore changes directly from
`AION_RUNTIME_LEASE_HMAC_KEY` to `OMERTA_RUNTIME_LEASE_HMAC_KEY` without a legacy
alias. Its not-yet-deployed signature domain changes directly from
`AION_RUNTIME_LEASE_V1` to `OMERTA_RUNTIME_LEASE_V1`.

The lease TTL, maximum TTL and persistent fence path use the canonical
`OMERTA_RUNTIME_LEASE_*` names. Their previously documented `AION_*` names remain
temporary nonsecret aliases; conflicting canonical and legacy values fail
closed without including either value in diagnostics.

Standard ecosystem variables such as `DATABASE_URL`, `NEXTAUTH_*`, `VAULT_*`,
`HTTP_PROXY` and `NO_PROXY` retain their external names. Historical branch names,
Git references and evidence documents remain historical facts. Database names,
roles, buckets, paths and persisted identifiers containing `aion` are data
migration concerns and are not renamed by configuration-key replacement.

The existing `OMERTAOS_*` installer variables are not changed in the first
migration slice. Their consolidation into `OMERTA_*` requires a separate native
deployment migration so installer, backup, rollback and restore contracts remain
coherent.

## Consequences

- `OMERTA_*` becomes the only namespace for new product-owned configuration.
- Compatibility is implemented in typed configuration readers, not scattered
  ad hoc fallbacks.
- Compose, systemd, examples and tests migrate with the owning service slice.
- A raw search-and-replace across all `AION_*` references is prohibited because
  it could silently break secrets, native deployment and persisted data access.
- ADR 0001 continues to define canonical service ownership; its AION wording is
  historical and does not define the configuration namespace.

## Rollback

Each migration slice is independently revertible while its legacy alias remains.
The R6.15 lease-name slice can be reverted before provisioning because no accepted
deployment uses either HMAC name or signature domain. Rollback must not copy,
print or commit a secret value.
