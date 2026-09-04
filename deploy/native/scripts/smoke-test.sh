#!/usr/bin/env bash
set -euo pipefail

MODE=native
TIMEOUT=5
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-}"
QUICKSTART_COMPOSE_FILE=
CONSOLE_PORT=
GATEWAY_PORT=
CONTROL_PORT=

usage() {
  cat <<'EOF'
Usage: smoke-test.sh [--mode native|quickstart] [--timeout SECONDS]
                     [--project-name NAME] [--help]

Read-only N7 acceptance checks. Native mode verifies data services, the N5
one-shot result, all N6 units, Runtime's binary healthcheck, listeners, HTTP
payloads, the Console-to-Gateway-to-Control chain, restart state, and journald.
Quickstart mode honors the OMERTA_*_HOST_PORT variables and checks the selected
Compose project. It never starts, stops, reloads, migrates, bootstraps, or
modifies a service.
EOF
}

die() { printf 'FAIL: %s\n' "$*" >&2; exit 1; }
pass() { printf 'PASS: %s\n' "$*"; }

resolve_host_alias() {
  local canonical_name="$1" legacy_name="$2" default_value="$3"
  local canonical_value="${!canonical_name-}" legacy_value="${!legacy_name-}"
  if [[ -n "$canonical_value" && -n "$legacy_value" && "$canonical_value" != "$legacy_value" ]]; then
    die "conflicting environment aliases: $canonical_name, $legacy_name"
  fi
  if [[ -n "$canonical_value" ]]; then
    printf '%s' "$canonical_value"
  elif [[ -n "$legacy_value" ]]; then
    printf 'WARNING: deprecated environment alias %s; use %s\n' "$legacy_name" "$canonical_name" >&2
    printf '%s' "$legacy_value"
  else
    printf '%s' "$default_value"
  fi
}

QUICKSTART_COMPOSE_FILE="$(resolve_host_alias OMERTA_QUICKSTART_COMPOSE_FILE AION_QUICKSTART_COMPOSE_FILE deploy/docker/compose/quickstart.yml)"
CONSOLE_PORT="$(resolve_host_alias OMERTA_CONSOLE_HOST_PORT AION_CONSOLE_HOST_PORT 3000)"
GATEWAY_PORT="$(resolve_host_alias OMERTA_GATEWAY_HOST_PORT AION_GATEWAY_HOST_PORT 8080)"
CONTROL_PORT="$(resolve_host_alias OMERTA_CONTROL_HOST_PORT AION_CONTROL_HOST_PORT 8000)"

while (($#)); do
  case "$1" in
    --mode) [[ $# -ge 2 ]] || die '--mode requires a value'; MODE="$2"; shift ;;
    --timeout) [[ $# -ge 2 ]] || die '--timeout requires a value'; TIMEOUT="$2"; shift ;;
    --project-name) [[ $# -ge 2 ]] || die '--project-name requires a value'; PROJECT_NAME="$2"; shift ;;
    --help|-h) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
  shift
done

[[ "$MODE" == native || "$MODE" == quickstart ]] || die 'mode must be native or quickstart'
[[ "$TIMEOUT" =~ ^[1-9][0-9]*$ ]] || die 'timeout must be a positive integer'

validate_port() {
  local name="$1" value="$2"
  [[ "$value" =~ ^[0-9]+$ ]] && ((value >= 1 && value <= 65535)) \
    || die "$name must be an integer between 1 and 65535"
}

quickstart_compose() {
  local args=(docker compose --project-directory "$REPO_ROOT")
  [[ -z "$PROJECT_NAME" ]] || args+=(--project-name "$PROJECT_NAME")
  args+=(-f "$QUICKSTART_COMPOSE_FILE")
  "${args[@]}" "$@"
}

fetch_json() {
  local name="$1" url="$2" output
  output="$(curl --fail --silent --show-error --max-time "$TIMEOUT" \
    --header 'Accept: application/json' "$url")" || die "$name is unreachable"
  jq -e . >/dev/null <<< "$output" || die "$name returned invalid JSON"
  printf '%s' "$output"
}

check_service_payload() {
  local name="$1" url="$2" service="$3" payload
  payload="$(fetch_json "$name" "$url")"
  jq -e --arg service "$service" '.status == "ok" and .service == $service' \
    >/dev/null <<< "$payload" || die "$name returned an unhealthy payload"
  pass "$name"
}

check_compose_health() {
  local name="$1" service="$2" container_id health
  container_id="$(quickstart_compose ps -q "$service")"
  [[ -n "$container_id" ]] || die "$name Quickstart container is missing"
  health="$(docker inspect --format '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$container_id")" \
    || die "$name Quickstart container is not inspectable"
  [[ "$health" == healthy ]] || die "$name Quickstart container is not healthy: $health"
  pass "$name Quickstart container"
}

check_quickstart_install() {
  local container_id state
  container_id="$(quickstart_compose ps --all -q install)"
  [[ -n "$container_id" ]] || die 'Quickstart install container is missing'
  state="$(docker inspect --format '{{.State.Status}}:{{.State.ExitCode}}' "$container_id")" \
    || die 'Quickstart install container is not inspectable'
  [[ "$state" == exited:0 ]] || die "Quickstart install container did not exit successfully: $state"
  pass 'Quickstart install container'
}

check_quickstart_runtime_registration() {
  quickstart_compose exec -T control python -c '
from datetime import UTC, datetime, timedelta
from control.app.network.models import SessionLocal
from control.app.runtime_nodes.lifecycle import RuntimeLifecycleConfig
from control.scheduling.models import RuntimeNode
configs = RuntimeLifecycleConfig.all_from_env()
if not configs:
    raise SystemExit(1)
with SessionLocal() as db:
    for config in configs:
        node = db.get(RuntimeNode, config.node_id)
        if node is None or node.state != "healthy" or node.last_heartbeat_at is None:
            raise SystemExit(1)
        heartbeat = node.last_heartbeat_at
        if heartbeat.tzinfo is None:
            heartbeat = heartbeat.replace(tzinfo=UTC)
        if datetime.now(UTC) - heartbeat > timedelta(seconds=30):
            raise SystemExit(1)
' >/dev/null || die 'Runtime Quickstart registration is missing or stale'
  pass 'Runtime Quickstart automatic registration'
}

check_quickstart() {
  for executable in curl jq; do command -v "$executable" >/dev/null || die "$executable is required"; done
  command -v docker >/dev/null || die 'docker is required for Quickstart readiness'
  [[ -z "$PROJECT_NAME" || "$PROJECT_NAME" =~ ^[a-z0-9][a-z0-9_-]*$ ]] \
    || die 'project name must start with a lowercase letter or digit and contain only lowercase letters, digits, hyphens, or underscores'
  if [[ "$QUICKSTART_COMPOSE_FILE" != /* ]]; then
    QUICKSTART_COMPOSE_FILE="$REPO_ROOT/$QUICKSTART_COMPOSE_FILE"
  fi
  [[ -f "$QUICKSTART_COMPOSE_FILE" ]] || die 'Quickstart Compose file is missing'
  validate_port OMERTA_CONSOLE_HOST_PORT "$CONSOLE_PORT"
  validate_port OMERTA_GATEWAY_HOST_PORT "$GATEWAY_PORT"
  validate_port OMERTA_CONTROL_HOST_PORT "$CONTROL_PORT"

  check_compose_health PostgreSQL postgres
  check_compose_health Redis redis
  check_compose_health Runtime runtime
  check_quickstart_install
  check_compose_health Control control
  check_compose_health Gateway gateway
  check_compose_health Console console
  quickstart_compose exec -T runtime /usr/local/bin/runtime-daemon --healthcheck >/dev/null \
    || die 'Runtime Quickstart healthcheck failed'
  pass 'Runtime Quickstart healthcheck'
  check_quickstart_runtime_registration

  check_service_payload Control "http://127.0.0.1:${CONTROL_PORT}/healthz" control
  local gateway console_chain
  gateway="$(fetch_json Gateway "http://127.0.0.1:${GATEWAY_PORT}/health")"
  jq -e '.status == "ok" and .service == "gateway" and
    .dependencies.redis == "ok" and .dependencies.control == "ok"' \
    >/dev/null <<< "$gateway" || die 'Gateway or a required dependency is degraded'
  pass 'Gateway and dependencies'
  check_service_payload Console "http://127.0.0.1:${CONSOLE_PORT}/health" console
  console_chain="$(fetch_json 'Console system health' "http://127.0.0.1:${CONSOLE_PORT}/api/system/health")"
  jq -e '.status == "ok" and
    .services.console.status == "ok" and
    .services.gateway.status == "ok" and
    .services.control.status == "ok"' \
    >/dev/null <<< "$console_chain" || die 'Canonical Console-to-Gateway-to-Control health chain is degraded'
  pass 'Canonical Console-to-Gateway-to-Control chain'
}

check_active_unit() {
  local unit="$1" expected_substate="${2:-running}" state substate result restarts
  state="$(systemctl show "$unit" --property=ActiveState --value)"
  substate="$(systemctl show "$unit" --property=SubState --value)"
  result="$(systemctl show "$unit" --property=Result --value)"
  restarts="$(systemctl show "$unit" --property=NRestarts --value)"
  [[ "$state" == active ]] || die "$unit is not active"
  [[ "$substate" == "$expected_substate" ]] || die "$unit has unexpected substate: $substate"
  [[ "$result" == success ]] || die "$unit result is not success"
  [[ "$restarts" =~ ^[0-9]+$ && "$restarts" -le 2 ]] || die "$unit is in a restart loop"
  pass "$unit active/$substate"
}

check_listener() {
  local port="$1" name="$2" loopback_only="$3" addresses address
  addresses="$(ss -H -ltn | awk -v suffix=":$port" \
    'substr($4, length($4)-length(suffix)+1) == suffix {print $4}')"
  [[ -n "$addresses" ]] || die "$name has no TCP listener on port $port"
  if "$loopback_only"; then
    while IFS= read -r address; do
      case "$address" in
        127.0.0.1:"$port"|\[::1\]:"$port") ;;
        *) die "$name exposes a non-loopback listener: $address" ;;
      esac
    done <<< "$addresses"
  fi
  pass "$name listener"
}

check_native() {
  [[ "$(uname -s)" == Linux ]] || die 'Native smoke requires Linux'
  [[ -d /run/systemd/system ]] || die 'systemd is not running'
  [[ "$(ps -p 1 -o comm= | tr -d '[:space:]')" == systemd ]] || die 'systemd is not PID 1'
  for executable in curl jq systemctl journalctl pg_isready redis-cli ss awk ps tr; do
    command -v "$executable" >/dev/null || die "$executable is required for Native smoke"
  done

  systemctl is-enabled --quiet omertaos.target || die 'omertaos.target is not enabled'
  pass 'omertaos.target enabled'
  systemctl is-active --quiet postgresql.service || die 'PostgreSQL service is not active'
  systemctl is-active --quiet redis-server.service || die 'Redis service is not active'
  pg_isready --host=127.0.0.1 --port=5432 --quiet || die 'PostgreSQL is not ready'
  [[ "$(redis-cli --host 127.0.0.1 --port 6379 --raw ping)" == PONG ]] || die 'Redis did not return PONG'
  pass 'PostgreSQL and Redis readiness'

  check_active_unit omertaos-install.service exited
  [[ "$(systemctl show omertaos-install.service --property=ExecMainStatus --value)" == 0 ]] \
    || die 'N5 install unit exited unsuccessfully'
  check_active_unit omertaos-runtime.service
  check_active_unit omertaos-control.service
  check_active_unit omertaos-gateway.service
  check_active_unit omertaos-console.service
  systemctl is-active --quiet omertaos.target || die 'omertaos.target is not active'
  pass 'omertaos.target active'

  [[ -L /opt/omertaos/current ]] || die 'active release symlink is missing'
  [[ -x /opt/omertaos/current/bin/runtime-daemon ]] || die 'Runtime binary is missing'
  OMERTA_RUNTIME_HEALTH_ADDR=127.0.0.1:50051 \
    /opt/omertaos/current/bin/runtime-daemon --healthcheck \
    || die 'Runtime binary healthcheck failed'
  pass 'Runtime binary healthcheck'

  check_listener 50051 Runtime true
  check_listener 8000 Control true
  check_listener 8080 Gateway false
  check_listener 3000 Console false

  check_service_payload Control http://127.0.0.1:8000/healthz control
  local gateway console_chain journal
  gateway="$(fetch_json Gateway http://127.0.0.1:8080/health)"
  jq -e '.status == "ok" and .service == "gateway" and
    .dependencies.redis == "ok" and .dependencies.control == "ok"' \
    >/dev/null <<< "$gateway" || die 'Gateway or a required dependency is degraded'
  pass 'Gateway and dependencies'
  check_service_payload Console http://127.0.0.1:3000/healthz console
  console_chain="$(fetch_json 'Console system health' http://127.0.0.1:3000/api/system/health)"
  jq -e '.status == "ok" and
    .services.console.status == "ok" and
    .services.gateway.status == "ok" and
    .services.control.status == "ok"' \
    >/dev/null <<< "$console_chain" || die 'Canonical Console-to-Gateway-to-Control health chain is degraded'
  pass 'Canonical Console-to-Gateway-to-Control chain'

  for unit in omertaos-install.service omertaos-runtime.service omertaos-control.service \
    omertaos-gateway.service omertaos-console.service; do
    journal="$(journalctl --quiet --no-pager --output=cat --unit "$unit" --lines 1)" \
      || die "journald is not readable for $unit"
    [[ -n "$journal" ]] || die "journald has no entry for $unit"
  done
  pass 'journald access for all Native units'
}

if [[ "$MODE" == native ]]; then check_native; else check_quickstart; fi
printf 'OMERTAOS %s smoke test passed.\n' "$MODE"
