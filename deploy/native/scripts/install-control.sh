#!/usr/bin/env bash
set -euo pipefail

DRY_RUN=false
CHECK_ONLY=false
ROOT="${OMERTAOS_ROOT:-/opt/omertaos/current}"
VENV="${OMERTAOS_CONTROL_VENV:-/var/lib/omertaos/venvs/control}"
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=_install-lib.sh
source "$SCRIPT_DIR/_install-lib.sh"

usage() { cat <<'EOF'
Usage: install-control.sh [--root PATH] [--venv PATH] [--dry-run|--check] [--help]

Create/update the Control virtualenv as omertaos and verify its canonical ASGI
entrypoint. This installer does not connect to databases, migrate, seed, or start services.
EOF
}
while (($#)); do case "$1" in
  --root) (($# >= 2)) || native_die '--root requires a path'; ROOT="$2"; shift ;;
  --venv) (($# >= 2)) || native_die '--venv requires a path'; VENV="$2"; shift ;;
  --dry-run) DRY_RUN=true ;; --check) CHECK_ONLY=true ;;
  --help|-h) usage; exit 0 ;; *) native_die "unknown argument: $1" ;;
esac; shift; done
"$DRY_RUN" && "$CHECK_ONLY" && native_die '--dry-run and --check are mutually exclusive'
native_require_linux
native_prepare_runner
command -v python3 >/dev/null || native_die 'python3 is required; complete N2 first'
python3 -c 'import sys; raise SystemExit(0 if (3, 11) <= sys.version_info < (3, 13) else 1)' \
  || native_die 'Python must satisfy >=3.11,<3.13'
[[ -f "$ROOT/pyproject.toml" && -f "$ROOT/control/app/main.py" ]] || native_die 'canonical Control sources are missing'

if "$CHECK_ONLY"; then
  [[ -x "$VENV/bin/python" && -x "$VENV/bin/uvicorn" ]] || native_die 'Control virtualenv artifacts are missing'
else
  native_prepare_dir "$(dirname "$VENV")"
  native_prepare_dir /var/lib/omertaos/control
  [[ -x "$VENV/bin/python" ]] || native_run_service python3 -m venv "$VENV"
  native_run_service "$VENV/bin/python" -m pip install --disable-pip-version-check -e "$ROOT[control]"
fi

if ! "$DRY_RUN"; then
  native_run_service env OMERTA_CONTROL_DATA_DIR=/var/lib/omertaos/control PYTHONPATH="$ROOT" \
    "$VENV/bin/python" -c 'from control.app.main import app; assert app is not None'
  native_run_service "$VENV/bin/python" -m pip check
fi
printf 'N4 Control build/install checks completed; no service was started.\n'
