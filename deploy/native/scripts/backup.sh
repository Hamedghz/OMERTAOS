#!/usr/bin/env bash
set -euo pipefail

DEST=
DRY_RUN=false
CONTROL_ENV=/etc/omertaos/control.env
CONSOLE_ENV=/etc/omertaos/console.env

usage() {
  cat <<'EOF'
Usage: backup.sh --dest EXTERNAL_DIRECTORY [--dry-run] [--help]

Create a new timestamped PostgreSQL/Redis/config backup with SHA-256 manifest.
The destination must be outside /opt/omertaos, /var/lib/omertaos, and
/etc/omertaos. Existing backup directories are never overwritten or deleted.
EOF
}
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
while (($#)); do case "$1" in
  --dest) (($# >= 2)) || die '--dest requires a path'; DEST="$2"; shift ;;
  --dry-run) DRY_RUN=true ;;
  --help|-h) usage; exit 0 ;;
  *) die "unknown argument: $1" ;;
esac; shift; done

[[ "$(uname -s)" == Linux ]] || die 'Native backup requires Linux'
((EUID == 0)) || die 'run as root'
[[ -n "$DEST" ]] || die '--dest is required'
for executable in pg_dump redis-cli tar sha256sum install date readlink grep; do
  command -v "$executable" >/dev/null || die "missing required executable: $executable"
done
[[ -d "$DEST" ]] || die 'external backup destination must already exist'
DEST="$(readlink -f -- "$DEST")"
case "$DEST" in
  /opt/omertaos|/opt/omertaos/*|/var/lib/omertaos|/var/lib/omertaos/*|/etc/omertaos|/etc/omertaos/*)
    die 'backup destination must be external to installation, state, and configuration roots' ;;
esac
[[ -f "$CONTROL_ENV" && -f "$CONSOLE_ENV" ]] || die 'database environment files are missing'

read_value() {
  local file="$1" key="$2"
  grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2- || true
}
read_compatible_value() {
  local file="$1" canonical_name="$2" legacy_name="$3" canonical_value legacy_value
  canonical_value="$(read_value "$file" "$canonical_name")"
  legacy_value="$(read_value "$file" "$legacy_name")"
  if [[ -n "$canonical_value" && -n "$legacy_value" && "$canonical_value" != "$legacy_value" ]]; then
    die "conflicting environment aliases: $canonical_name, $legacy_name"
  fi
  if [[ -n "$canonical_value" ]]; then
    printf '%s' "$canonical_value"
  else
    [[ -z "$legacy_value" ]] || printf 'WARNING: deprecated environment alias %s; use %s\n' "$legacy_name" "$canonical_name" >&2
    printf '%s' "$legacy_value"
  fi
}
control_dsn="$(read_compatible_value "$CONTROL_ENV" OMERTA_CONTROL_POSTGRES_DSN AION_CONTROL_POSTGRES_DSN)"
console_dsn="$(read_value "$CONSOLE_ENV" DATABASE_URL)"
[[ "$control_dsn" == postgres* && "$console_dsn" == postgres* ]] || die 'PostgreSQL DSNs are missing'

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
backup="$DEST/omertaos-$stamp"
[[ ! -e "$backup" ]] || die 'backup directory already exists'
if "$DRY_RUN"; then
  printf 'DRY-RUN: create %q with two PostgreSQL custom dumps, Redis RDB, sanitized configuration archive, metadata, and SHA-256 manifest\n' "$backup"
  exit 0
fi

install -d -o root -g root -m 0700 "$backup"
pg_dump --format=custom --no-owner --no-privileges --dbname="$control_dsn" --file="$backup/control.pgdump"
pg_dump --format=custom --no-owner --no-privileges --dbname="$console_dsn" --file="$backup/console.pgdump"
redis_dir="$(redis-cli --raw CONFIG GET dir | tail -n 1)"
redis_file="$(redis-cli --raw CONFIG GET dbfilename | tail -n 1)"
redis-cli --raw BGSAVE >/dev/null
for _ in {1..60}; do
  [[ "$(redis-cli --raw LASTSAVE)" != 0 && -s "$redis_dir/$redis_file" ]] && break
  sleep 1
done
[[ -s "$redis_dir/$redis_file" ]] || die 'Redis snapshot was not created'
install -o root -g root -m 0600 "$redis_dir/$redis_file" "$backup/redis.rdb"
tar --create --gzip --file="$backup/config.tar.gz" \
  --exclude='*.env' --exclude='secrets' -C / etc/omertaos
printf 'created_utc=%s\nhost=%s\nformat_version=1\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$(hostname)" > "$backup/backup.metadata"
(cd "$backup" && sha256sum control.pgdump console.pgdump redis.rdb config.tar.gz backup.metadata > backup.manifest.sha256)
(cd "$backup" && sha256sum --check backup.manifest.sha256)
printf 'Verified Native backup created at %s\n' "$backup"
