#!/usr/bin/env bash
set -euo pipefail
umask 077

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
COMPOSE_FILE="deploy/docker/compose/quickstart.yml"
cd "${ROOT_DIR}"

export COMPOSE_PROJECT_NAME=${COMPOSE_PROJECT_NAME:-omertaos}

PYTHON_BIN="${PYTHON_BIN:-}"
if [ -z "$PYTHON_BIN" ]; then
  if command -v python3 >/dev/null 2>&1; then
    PYTHON_BIN="python3"
  elif command -v python >/dev/null 2>&1; then
    PYTHON_BIN="python"
  else
    echo "Python is required but was not found. Please install python3." >&2
    exit 1
  fi
fi

"$PYTHON_BIN" scripts/validate_environment_aliases.py \
  --reject-legacy-secrets --quiet

if [ ! -f dev.env ]; then
  echo "dev.env missing; aborting." >&2
  exit 1
fi

created_env=false
if [ ! -f .env ]; then
  cp dev.env .env
  created_env=true
  echo "Created .env from dev.env"
else
  backup_path=".env.bak.$(date +%s)"
  cp -p .env "$backup_path"
  chmod 0600 "$backup_path"
  echo "Backed up existing .env"
fi
chmod 0600 .env

"$PYTHON_BIN" scripts/validate_environment_aliases.py \
  --migrate-env-file .env --quiet

read_env_value() {
  local key="$1"
  "$PYTHON_BIN" -c \
    'from pathlib import Path; import sys; from scripts.validate_environment_aliases import parse_environment_file; value = parse_environment_file(Path(".env")).get(sys.argv[1]); sys.stdout.write(value or "")' \
    "$key"
}

set_env() {
  local key="$1" value="$2"
  printf '%s' "$value" | "$PYTHON_BIN" -c \
    'from pathlib import Path; import sys; from scripts.validate_environment_aliases import update_environment_file; update_environment_file(Path(".env"), {sys.argv[1]: sys.stdin.read()})' \
    "$key"
}

generate_alnum() {
  "$PYTHON_BIN" -c \
    'import secrets, string, sys; alphabet = string.ascii_letters + string.digits; sys.stdout.write("".join(secrets.choice(alphabet) for _ in range(int(sys.argv[1]))))' \
    "$1"
}

generate_hex() {
  "$PYTHON_BIN" -c 'import secrets, sys; sys.stdout.write(secrets.token_hex(int(sys.argv[1])))' "$1"
}

resolve_value() {
  local canonical_name="$1" legacy_name="$2" default_value="$3"
  local resolved="${!canonical_name:-}"
  if [ -z "$resolved" ] && [ -n "$legacy_name" ]; then
    resolved="${!legacy_name:-}"
  fi
  if [ -z "$resolved" ]; then
    resolved="$(read_env_value "$canonical_name")"
  fi
  printf '%s' "${resolved:-$default_value}"
}

resolve_install_secret() {
  local key="$1" generated_value="$2"
  local resolved="${!key:-}"
  if [ -z "$resolved" ] && [ "$created_env" = false ]; then
    resolved="$(read_env_value "$key")"
  fi
  printf '%s' "${resolved:-$generated_value}"
}

encode_uri_component() {
  printf '%s' "$1" | "$PYTHON_BIN" -c \
    'import sys; from urllib.parse import quote; sys.stdout.write(quote(sys.stdin.read(), safe=""))'
}

DEV_ADMIN_EMAIL_VALUE="$(resolve_value DEV_ADMIN_EMAIL '' dev-admin@omerta.local)"
DEV_ADMIN_PASSWORD_VALUE="$(resolve_install_secret DEV_ADMIN_PASSWORD "$(generate_alnum 24)")"
DEV_API_KEY_VALUE="$(resolve_install_secret DEV_API_KEY "$(generate_hex 16)")"
GATEWAY_ADMIN_TOKEN="$(resolve_install_secret OMERTA_GATEWAY_ADMIN_TOKEN "$DEV_API_KEY_VALUE")"
GATEWAY_API_KEYS="$(resolve_install_secret OMERTA_GATEWAY_API_KEYS "${DEV_API_KEY_VALUE}:admin")"
DEV_ADMIN_TOKEN="$(resolve_install_secret OMERTA_DEV_ADMIN_TOKEN "$DEV_API_KEY_VALUE")"
NEXTAUTH_SECRET_VALUE="$(resolve_install_secret NEXTAUTH_SECRET "$(generate_hex 32)")"

DB_USER="$(resolve_value OMERTA_DB_USER AION_DB_USER aion)"
DB_PASSWORD="$(resolve_install_secret OMERTA_DB_PASSWORD "$(generate_alnum 32)")"
DB_NAME="$(resolve_value OMERTA_DB_NAME AION_DB_NAME omerta_db)"
DB_HOST="$(resolve_value OMERTA_DB_HOST AION_DB_HOST postgres)"
MINIO_SECRET="$(resolve_install_secret OMERTA_CONTROL_MINIO_SECRET_KEY "$(generate_alnum 32)")"
ENCODED_DB_USER="$(encode_uri_component "$DB_USER")"
ENCODED_DB_PASSWORD="$(encode_uri_component "$DB_PASSWORD")"
ENCODED_DB_NAME="$(encode_uri_component "$DB_NAME")"
CONTROL_POSTGRES_DSN="postgresql://${ENCODED_DB_USER}:${ENCODED_DB_PASSWORD}@${DB_HOST}:5432/${ENCODED_DB_NAME}"
PRISMA_DATABASE_URL="${CONTROL_POSTGRES_DSN}?schema=public"

set_env "OMERTA_DB_USER" "$DB_USER"
set_env "OMERTA_DB_PASSWORD" "$DB_PASSWORD"
set_env "OMERTA_DB_NAME" "$DB_NAME"
set_env "OMERTA_DB_HOST" "$DB_HOST"
set_env "DATABASE_URL" "${PRISMA_DATABASE_URL}"
set_env "OMERTA_CONTROL_POSTGRES_DSN" "${CONTROL_POSTGRES_DSN}"
set_env "OMERTA_CONTROL_MINIO_SECRET_KEY" "$MINIO_SECRET"
set_env "CONSOLE_ADMIN_EMAIL" "${DEV_ADMIN_EMAIL_VALUE}"
set_env "CONSOLE_ADMIN_PASSWORD" "${DEV_ADMIN_PASSWORD_VALUE}"
set_env "DEV_ADMIN_EMAIL" "${DEV_ADMIN_EMAIL_VALUE}"
set_env "DEV_ADMIN_PASSWORD" "${DEV_ADMIN_PASSWORD_VALUE}"
set_env "DEV_API_KEY" "${DEV_API_KEY_VALUE}"
set_env "OMERTA_GATEWAY_API_KEYS" "${GATEWAY_API_KEYS}"
set_env "OMERTA_GATEWAY_ADMIN_TOKEN" "${GATEWAY_ADMIN_TOKEN}"
set_env "OMERTA_DEV_ADMIN_TOKEN" "${DEV_ADMIN_TOKEN}"
set_env "NEXTAUTH_SECRET" "${NEXTAUTH_SECRET_VALUE}"
set_env "OMERTA_DOCKER" "1"
set_env "OMERTA_GATEWAY_PORT" "8080"
set_env "CONSOLE_PORT" "3000"
set_env "NEXTAUTH_URL" "http://localhost:3000"
set_env "CONTROL_URL" "http://control:8000"
set_env "GATEWAY_URL" "http://gateway:8080"
set_env "OMERTA_GATEWAY_URL" "http://gateway:8080"
set_env "CONSOLE_URL" "http://localhost:3000"
set_env "NEXT_PUBLIC_GATEWAY_URL" "http://localhost:8080"

"$PYTHON_BIN" scripts/validate_environment_aliases.py \
  --env-file .env --reject-legacy-secrets --quiet

check_port() {
  local port="$1"
  if command -v ss >/dev/null 2>&1; then
    ss -ltn | awk '{print $4}' | grep -E "(^|:)${port}$" >/dev/null 2>&1
  elif command -v lsof >/dev/null 2>&1; then
    lsof -i tcp:"${port}" -sTCP:LISTEN >/dev/null 2>&1
  else
    return 1
  fi
}

for port in 3000 8080 8000; do
  if check_port "$port"; then
    echo "Port ${port} is already in use. Please free it before continuing." >&2
    exit 1
  fi
done

existing_stack="$(docker compose --project-directory . -f "$COMPOSE_FILE" ps -q || true)"
if [ -n "$existing_stack" ]; then
  echo "Stopping existing OMERTAOS stack..."
  docker compose --project-directory . -f "$COMPOSE_FILE" down
fi

echo "Generating self-signed certificates (dev only)..."
mkdir -p config/certs/dev config/keys
openssl req -x509 -newkey rsa:2048 -nodes -keyout config/certs/dev/dev.key -out config/certs/dev/dev.crt -days 365 -subj "/CN=localhost"
openssl genrsa -out config/keys/dev-jwt.key 2048
openssl rsa -in config/keys/dev-jwt.key -pubout -out config/keys/dev-jwt.pub

cat <<'NOTE'
WARNING: The generated certificates and keys are for development only.
Replace them with production-grade secrets and rotate any placeholder tokens
(DEV_SECRET_PLACEHOLDER) before deploying.
NOTE

echo "Starting stack with docker compose..."
docker compose --project-directory . -f "$COMPOSE_FILE" up --build -d

cat <<EOF

Quick install completed.
Services: control:8000, gateway:8080, console:3000

Local development credentials are stored in .env with mode 0600.
Their values are intentionally not printed.

You can re-run this bootstrap safely via: make bootstrap
EOF
