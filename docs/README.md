# OMERTAOS documentation map

This index separates current engineering contracts, research evidence,
operational guidance, and historical migration records. That distinction is
important when evaluating OMERTAOS: a design document states intended
properties; only source, tests, and recorded validation support an implemented
claim.

## Start here

| Reader | Recommended path |
|---|---|
| Researcher or reviewer | [Research package](research/README.md) -> [Evidence and claims](research/evidence-and-claims.md) -> [Reproducibility](research/reproducibility.md) |
| Architect | [Technical architecture](../ARCHITECTURE.md) -> [Repository ownership](../STRUCTURE.md) -> [ADR 0001](adr/0001-canonical-aion-ownership.md) |
| Contributor | [Contributing](../CONTRIBUTING.md) -> component README -> [Test strategy](../tests/README.md) |
| Security reviewer | [Security policy](../SECURITY.md) -> [Evidence and claims](research/evidence-and-claims.md) -> Runtime README |
| Operator | [Deployment index](../deploy/README.md) -> CAPO/native guidance -> acceptance report |
| COMEX reviewer or sponsor | [COMEX readiness program](comex/README.fa.md) -> [Progress and evidence ledger](comex/progress.fa.md) |

## Current normative documents

These documents define the repository's present ownership and contribution
rules:

- [README](../README.md): public project and research entry point;
- [ARCHITECTURE](../ARCHITECTURE.md): technical boundary and protocol model;
- [STRUCTURE](../STRUCTURE.md): canonical directory ownership;
- [ADR 0001](adr/0001-canonical-aion-ownership.md): accepted ownership decision;
- [ADR 0002](adr/0002-omerta-configuration-namespace.md): canonical `OMERTA_*`
  configuration namespace and compatibility rules;
- [Canonical paths](migration/canonical-paths.md): migration and compatibility
  map;
- [Security policy](../SECURITY.md): disclosure scope and supported branch.

When these documents disagree with code, current tests and source are the
primary implementation evidence; the discrepancy should be reported and
corrected.

## Research package

The [research package](research/README.md) is written for thesis supervisors,
reviewers, and prospective collaborators. It includes:

- the problem statement and architectural novelty;
- a claim-to-evidence ledger;
- a reproducibility protocol;
- manuscript-to-repository alignment;
- explicit limitations and a validation roadmap.

The package does not assert paper acceptance, a DOI, benchmark results,
production deployment, security certification, or formal verification.

## Component documentation

| Component | Documentation | Responsibility |
|---|---|---|
| Console | [console/README](../console/README.md) | Operator presentation and Gateway-facing client |
| Gateway | [gateway/README](../gateway/README.md) | External admission and transport boundary |
| Control | [control/README](../control/README.md) | Orchestration and durable decisions |
| Runtime | [runtime-daemon/README](../runtime-daemon/README.md) | Privileged execution boundary |
| Data | [data/README](../data/README.md) | Persistence and retrieval adapters |
| Registry | [registry/README](../registry/README.md) | Agent/model metadata ownership |
| Policies | [policies/README](../policies/README.md) | Policy definitions and evaluator contracts |
| Schemas | [schemas/README](../schemas/README.md) | Versioned source contracts |
| Tests | [tests/README](../tests/README.md) | Verification strategy and current CI scope |

## Operational and historical records

- `docs/comex/` defines the exhibition-readiness program and maintains its
  dated, evidence-backed progress ledger.
- `docs/capo/` and `deploy/CAPO/` contain CAPO installation, test, rollback,
  and acceptance material.
- `docs/migration/` records structure migration decisions and validation
  evidence. Dated reports are historical snapshots, not automatically
  current-state claims.
- `docs/migration/evidence/` preserves retired inputs for auditability. It is
  not an active implementation tree.
- `.agents/` and `.codex/` are engineering-assistant instructions and local
  workflow support, not product or scientific evidence.

## Document status convention

New or revised technical documents should state one of these roles where
ambiguity is possible:

- **Normative:** current architecture or policy contract.
- **Evidence:** reproducible observation tied to a commit, date, and command.
- **Design target:** intended behavior not yet demonstrated.
- **Historical:** retained migration or decision record.

Avoid unqualified words such as “secure,” “scalable,” “production-ready,” or
“validated.” Name the threat model, workload, environment, and supporting
evidence instead.
