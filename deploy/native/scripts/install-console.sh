#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CHECK_ONLY=false
ROOT="${OMERTAOS_ROOT:-/opt/omertaos/current}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_install-lib.sh
source "$SCRIPT_DIR/_install-lib.sh"

usage() { cat <<'EOF'
Usage: install-console.sh [--root PATH] [--dry-run|--check] [--help]

Install Console from pnpm-lock.yaml, generate Prisma client code, and build the
Next.js production artifact as omertaos. It does not migrate or contact a database.
EOF
}
while (($#)); do case "$1" in
  --root) (($# >= 2)) || native_die '--root requires a path'; ROOT="$2"; shift ;;
  --dry-run) DRY_RUN=true ;; --check) CHECK_ONLY=true ;;
  --help|-h) usage; exit 0 ;; *) native_die "unknown argument: $1" ;;
esac; shift; done
"$DRY_RUN" && "$CHECK_ONLY" && native_die '--dry-run and --check are mutually exclusive'
native_require_linux
native_prepare_runner
native_require_node
command -v corepack >/dev/null || native_die 'corepack is required for Console pnpm'
SERVICE="$ROOT/console"
[[ -f "$SERVICE/package.json" && -f "$SERVICE/pnpm-lock.yaml" ]] || native_die 'Console package or lockfile is missing'

if ! "$CHECK_ONLY"; then
  native_assert_service_writable "$SERVICE"
  native_prepare_dir /var/lib/omertaos/cache/pnpm
  native_run_service env COREPACK_HOME=/var/lib/omertaos/cache/corepack PNPM_HOME=/var/lib/omertaos/cache/pnpm \
    corepack pnpm --dir "$SERVICE" install --frozen-lockfile
  native_run_service env DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build OMERTA_ENABLE_PRISMA=0 \
    corepack pnpm --dir "$SERVICE" run prisma:generate
  native_run_service env DATABASE_URL=postgresql://build:build@127.0.0.1:5432/build OMERTA_ENABLE_PRISMA=0 \
    NEXT_PUBLIC_GATEWAY_URL=http://127.0.0.1:8080 NEXTAUTH_URL=http://127.0.0.1:3000 \
    NEXTAUTH_SECRET=n4-build-only-placeholder corepack pnpm --dir "$SERVICE" run build
  native_run_service corepack pnpm --dir "$SERVICE" exec tsc --project scripts/tsconfig.json
fi
if ! "$DRY_RUN"; then
  [[ -f "$SERVICE/.next/BUILD_ID" ]] || native_die 'Console build did not create .next/BUILD_ID'
  [[ -x "$SERVICE/node_modules/.bin/next" ]] || native_die 'Console Next.js executable is missing'
  [[ -f "$SERVICE/scripts/dist/bootstrap-admin.js" ]] || native_die 'Console bootstrap artifact is missing'
fi
printf 'N4 Console build/install checks completed; no migration or service start occurred.\n'
