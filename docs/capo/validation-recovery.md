# CAPO validation, troubleshooting, and recovery

Phase 6 validates the Native and Docker Quickstart paths without treating one
as proof of the other. No legacy path may be retired until both acceptance
columns are complete and reviewed by a human.

## Validation sequence

From the repository root, validate configuration and static contracts first:

```powershell
docker compose --project-directory . -f deploy/docker/compose/quickstart.yml config --quiet
powershell -NoProfile -File deploy/CAPO/tests/contract-tests.ps1
python -m pytest tests/architecture -q
```

On the intended Debian/Ubuntu SSD host, run the read-only Native probe after
first boot:

```bash
bash deploy/native/scripts/smoke-test.sh --mode native
```

For a running Quickstart stack, run:

```bash
bash deploy/native/scripts/smoke-test.sh --mode quickstart \
  --project-name "${COMPOSE_PROJECT_NAME:-omertaos}"
```

For an isolated stack, export the same `OMERTA_CONSOLE_HOST_PORT`,
`OMERTA_GATEWAY_HOST_PORT`, and `OMERTA_CONTROL_HOST_PORT` values used at startup.
The probe resolves containers through the selected project, checks the
one-shot installer result, and rejects unhealthy containers before probing the
host HTTP endpoints.

The Native probe requires PostgreSQL/Redis readiness, a successful N5 one-shot
unit, all N6 application units and the aggregate target, Runtime's binary
healthcheck, loopback-only Runtime/Control listeners, healthy JSON payloads,
healthy Gateway dependencies, the canonical Console-to-Gateway-to-Control
chain, bounded restart counts, and journald visibility. Quickstart remains a
separate compatibility probe and requires its Runtime container to be running;
the Compose healthcheck remains the authoritative gRPC readiness probe there.

## Troubleshooting

- Control failure: check PostgreSQL and Redis readiness, then inspect
  `journalctl -u omertaos-control.service` or Quickstart Control logs. Do not
  replace missing required stores with memory-only state.
- Gateway failure: verify Control health and `OMERTA_CONTROL_BASE_URL`; Gateway
  must route to Control rather than bypass it.
- Console failure: distinguish browser `NEXT_PUBLIC_GATEWAY_URL` from the
  server-side Gateway address and confirm port `3000` is free.
- Runtime failure: inspect the Runtime unit/container and bind address
  `127.0.0.1:50051` (Native) or `0.0.0.0:50051` inside Quickstart. Do not add
  unsupported runtime flags.
- Optional MongoDB, Qdrant, or MinIO failure: keep its `CAPO_*_ENABLED` flag
  false until the endpoint and credentials are validated. The capability must
  remain explicitly degraded without weakening authorization.

## Versioned update and non-destructive rollback

### Quickstart P3 boundary

`scripts/validate_quickstart_recovery.py` is an explicitly opted-in, bounded
fresh-install/restart probe, not a backup/restore tool. It reuses the validated
application images and an existing provisioned env/lease key. It refuses to
take over running test projects, rejects foreign/active volume consumers,
creates distinct fresh volumes and stops each project without deleting data.
Use a new `--fresh-project omerta-p3-fresh-<unique-suffix>` for another fresh
attempt; retained volumes must never be deleted to make the fresh check pass.
See the P3 entry in `acceptance-report.md` for the actual invocation and limits.

This restart-only gate exits 2 even when restart probes pass; it does not run
the separate encrypted-backup/restore or older-release-upgrade gates. Gateway
Redis cache replay does not prove durable Control result recovery. Control
currently rejects dispatched-task replay after process restart rather than
returning the lost result or executing it again.

The legacy `deploy/docker/scripts/backup.sh` archives only repository folders;
its paired restore copies files into the working directory. They do not export
PostgreSQL, MongoDB, MinIO, Qdrant or the paired Runtime fencing state/key, and
must not be used as a sensitive-data or P3 disaster-recovery procedure.
The user subsequently authorized local recovery-key creation. The dedicated
`scripts/quickstart_encrypted_recovery.py` acceptance tool now signs/encrypts
six stopped volumes, env/config and the paired lease key. It checks signatures,
encrypted-message integrity and archive paths before extracting into new
volumes, compares content/ownership/mode inventories before startup, and then
checks restored historical fixtures and authenticated canonical execution.
The local same-image restore passed. A separate historical upgrade harness
subsequently passed against the actual retained R6 single-worker dataset.
See the newer P3 report for exact evidence and reproduction.

Key/backup paths must be separate, owner-only and outside every Git worktree.
`--create-key --run` requires new paths; `--existing-backup --run` reuses the
protected exported key and signed backup but requires a NEW restore project.
The latter is a scoped validation workflow with source safety checks, not a
source-free disaster-recovery installer. New logical exports go under a unique
`exports-<restore-project>/` directory. The first run's exports remain at root.
No existing backup/key/volume is overwritten or deleted. Both dedicated key
agent caches are cleared on completion. Retain recovery keys and passphrase;
same-host storage does not cover host loss. Off-host custody, separate logical
restore and portable MinIO/Qdrant API exports need their own validation.
Preserve source volumes and test genuine older-release data on a restored clone
separately from a fresh install or reapplication of the same images.
No native/systemd acceptance is implied by these Docker probes.

`scripts/validate_historical_quickstart_upgrade.py --run` uses only the retained
stopped `omertaos-r6-fixed` source and a new `omerta-p3-restore-*` target. It also
preserves anonymous Redis/Mongo configdb volumes and Qdrant's original container
writable-layer data; those must not be mistaken for absent data. It hashes all
old database rows/columns before forward migrations, verifies preservation, then
validates the current authenticated canonical path with retained credentials.
The old Console is not started. Original services, volumes and writable-layer
data remain unchanged. Original cold backup is the recovery point; an automatic
database downgrade or running-old-code rollback is not tested.

P3's bounded local gates are now complete. Individual older reports may still
say `partial-blocked` because they cover only their own subset; use the latest
historical-upgrade result and current evidence ledger for aggregate status.
Do not infer arbitrary-version upgrades, nonempty encrypted proxy/configuration
migration, host-loss recovery or production acceptance from this one dataset.

### Native release workflow

Create a verified external backup, preview the immutable release build, and
activate only after the preview is reviewed:

```bash
bash deploy/native/scripts/update.sh --version 1.2.3 \
  --source /srv/omertaos-source \
  --backup /mnt/backup/omertaos-before-1.2.3 \
  --dry-run
bash deploy/native/scripts/update.sh --version 1.2.3 \
  --source /srv/omertaos-source \
  --backup /mnt/backup/omertaos-before-1.2.3 \
  --start
bash deploy/native/scripts/rollback.sh --check
bash deploy/native/scripts/rollback.sh --dry-run
bash deploy/native/scripts/rollback.sh --start
```

Update builds all four services under `/opt/omertaos/releases/<version>`, writes
a critical-artifact checksum manifest, applies only forward migrations, and
atomically changes `/opt/omertaos/current`. The prior code remains addressable
through `/opt/omertaos/previous`. Rollback verifies that immutable release and
changes only these code links plus the aggregate application target.

Both flows preserve `/etc/omertaos`, `/var/lib/omertaos`, the service account,
PostgreSQL roles/databases, Redis state, and every release. They never perform a
database downgrade. If a forward migration is incompatible with the selected
older code, keep services stopped and use the separately reviewed restore
procedure with the verified external backup.

Quickstart rollback is `docker compose --project-directory . -f deploy/docker/compose/quickstart.yml down`
without `--volumes`; named volumes and data remain intact.

## Local proxy secret permissions

On the Linux Quickstart, the local encrypted proxy-secret provider creates its
directory with mode `0700` and atomically replaces encrypted files with mode
`0600`. Existing directories must belong to the service UID, have no access for
others, and have no group-write bit. An owner-controlled `0750` native directory
remains supported. Directory and read-file symlinks are rejected; failed permission
or write operations are errors rather than successful writes. The AES-GCM file
format, encryption key and legacy configuration aliases are unchanged.

Before changing an existing directory, inspect ownership and active bind-mount
consumers. Apply a narrowly scoped permission repair as its owner, never recursive
permission changes or a key reset. Keep operator `.env` files at `0600`; provisioning
to a service with another UID requires its existing explicit secret-mount workflow,
not opening host secret files to all users. Never put real values in command logs.

## Acceptance state

Static validation on Windows can confirm syntax, contracts, Compose rendering,
and application tests. It cannot prove native systemd, ownership, package, or
SSD behavior. Those Native checks remain pending until recorded from the real
Linux host. A full running Quickstart smoke is also recorded independently;
configuration rendering alone is not runtime acceptance.
