#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CHECK_ONLY=false
ROOT="${OMERTAOS_ROOT:-/opt/omertaos/current}"
VENV="${OMERTAOS_CONTROL_VENV:-/var/lib/omertaos/venvs/control}"
CONTROL_ENV=/etc/omertaos/control.env
CONSOLE_ENV=/etc/omertaos/console.env
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_install-lib.sh
source "$SCRIPT_DIR/_install-lib.sh"

usage() { cat <<'EOF'
Usage: migrate-database.sh [--root PATH] [--venv PATH]
       [--control-env PATH] [--console-env PATH] [--dry-run|--check] [--help]

Apply the additive Control schema and committed Console Prisma migrations to
their distinct PostgreSQL databases. --check only reports missing migrations.
No seed, bootstrap, destructive SQL, or service start is performed.
EOF
}
while (($#)); do case "$1" in
  --root) (($# >= 2)) || native_die '--root requires a path'; ROOT="$2"; shift ;;
  --venv) (($# >= 2)) || native_die '--venv requires a path'; VENV="$2"; shift ;;
  --control-env) (($# >= 2)) || native_die '--control-env requires a path'; CONTROL_ENV="$2"; shift ;;
  --console-env) (($# >= 2)) || native_die '--console-env requires a path'; CONSOLE_ENV="$2"; shift ;;
  --dry-run) DRY_RUN=true ;; --check) CHECK_ONLY=true ;;
  --help|-h) usage; exit 0 ;; *) native_die "unknown argument: $1" ;;
esac; shift; done
"$DRY_RUN" && "$CHECK_ONLY" && native_die '--dry-run and --check are mutually exclusive'
native_require_linux
native_prepare_runner
native_require_node
command -v corepack >/dev/null || native_die 'corepack is required for Console migrations'
[[ -x "$VENV/bin/python" ]] || native_die 'Control virtualenv is missing; complete N4 first'
[[ -f "$ROOT/control/app/network/migrate.py" ]] || native_die 'Control migration entrypoint is missing'
[[ -f "$ROOT/console/prisma/schema.prisma" ]] || native_die 'Console Prisma schema is missing'
[[ -d "$ROOT/console/prisma/migrations" ]] || native_die 'Console migrations directory is missing'

declare -A CONTROL_CONFIG=() CONSOLE_CONFIG=()
native_load_env_file "$CONTROL_ENV" CONTROL_CONFIG
native_load_env_file "$CONSOLE_ENV" CONSOLE_CONFIG
canonical_control_dsn="${CONTROL_CONFIG[OMERTA_CONTROL_POSTGRES_DSN]:-}"
legacy_control_dsn="${CONTROL_CONFIG[AION_CONTROL_POSTGRES_DSN]:-}"
if [[ -n "$canonical_control_dsn" && -n "$legacy_control_dsn" && "$canonical_control_dsn" != "$legacy_control_dsn" ]]; then
  native_die 'conflicting environment aliases: OMERTA_CONTROL_POSTGRES_DSN, AION_CONTROL_POSTGRES_DSN'
fi
control_dsn="${canonical_control_dsn:-$legacy_control_dsn}"
if [[ -z "$canonical_control_dsn" && -n "$legacy_control_dsn" ]]; then
  printf 'WARNING: deprecated environment alias AION_CONTROL_POSTGRES_DSN; use OMERTA_CONTROL_POSTGRES_DSN\n' >&2
fi
console_dsn="${CONSOLE_CONFIG[DATABASE_URL]:-}"
for dsn in "$control_dsn" "$console_dsn"; do
  [[ "$dsn" == postgresql://* || "$dsn" == postgres://* ]] || native_die 'N5 requires PostgreSQL service DSNs'
  [[ "$dsn" != *CHANGE_ME* ]] || native_die 'N5 refuses placeholder database credentials'
  [[ "$dsn" == *@127.0.0.1:5432/* ]] || native_die 'Native PostgreSQL migrations must use 127.0.0.1:5432'
done
[[ "$control_dsn" != "$console_dsn" ]] || native_die 'Control and Console must use distinct PostgreSQL databases'
control_database="${control_dsn##*/}"; control_database="${control_database%%\?*}"
console_database="${console_dsn##*/}"; console_database="${console_database%%\?*}"
[[ -n "$control_database" && -n "$console_database" && "$control_database" != "$console_database" ]] \
  || native_die 'Control and Console database names must be distinct'

run_control() {
  local -a args=(-m control.app.network.migrate)
  "$CHECK_ONLY" && args+=(--check)
  if "$DRY_RUN"; then
    printf 'DRY-RUN: run Control migration as omertaos with OMERTA_CONTROL_POSTGRES_DSN=<redacted>\n'
  else
    native_run_service env OMERTA_CONTROL_POSTGRES_DSN="$control_dsn" PYTHONPATH="$ROOT" "$VENV/bin/python" "${args[@]}"
  fi
}
run_console() {
  local action=deploy
  "$CHECK_ONLY" && action=status
  if "$DRY_RUN"; then
    printf 'DRY-RUN: run prisma migrate deploy as omertaos with DATABASE_URL=<redacted>\n'
  else
    native_run_service env DATABASE_URL="$console_dsn" corepack pnpm --dir "$ROOT/console" exec prisma migrate "$action"
    if ! "$CHECK_ONLY"; then
      native_run_service env DATABASE_URL="$console_dsn" corepack pnpm --dir "$ROOT/console" exec prisma migrate status
    fi
  fi
}

run_control
run_console
printf 'N5 database migration phase completed; no seed, bootstrap, or service start occurred.\n'
