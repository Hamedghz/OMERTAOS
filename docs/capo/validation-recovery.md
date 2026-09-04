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

## Acceptance state

Static validation on Windows can confirm syntax, contracts, Compose rendering,
and application tests. It cannot prove native systemd, ownership, package, or
SSD behavior. Those Native checks remain pending until recorded from the real
Linux host. A full running Quickstart smoke is also recorded independently;
configuration rendering alone is not runtime acceptance.
