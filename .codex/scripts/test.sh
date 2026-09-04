#!/usr/bin/env bash
set -uo pipefail

echo "Running OMERTAOS tests..."

failures=()

run_check() {
  local name="$1"
  shift
  echo
  echo "==> $name"
  if "$@"; then
    echo "PASSED: $name"
  else
    local exit_code=$?
    echo "FAILED: $name (exit $exit_code)" >&2
    failures+=("$name")
  fi
}

python_cmd=()
if [ -x ".venv/bin/python" ]; then
  python_cmd=(".venv/bin/python")
elif command -v python3 >/dev/null 2>&1 && python3 -c "import sys" >/dev/null 2>&1; then
  python_cmd=("python3")
elif command -v python >/dev/null 2>&1 && python -c "import sys" >/dev/null 2>&1; then
  python_cmd=("python")
elif command -v py >/dev/null 2>&1 && py -3 -c "import sys" >/dev/null 2>&1; then
  python_cmd=("py" "-3")
fi

if [ "${#python_cmd[@]}" -gt 0 ] && [ -d "tests/architecture" ]; then
  run_check "Python architecture tests" "${python_cmd[@]}" -m pytest \
    tests/architecture -q -k "not test_structure_migration_gate"
elif [ -d "tests" ]; then
  echo "Python interpreter not found; Python tests cannot run." >&2
  failures+=("Python architecture tests")
fi

if command -v npm >/dev/null 2>&1; then
  if [ -f "gateway/package.json" ] && [ -d "tests/gateway" ]; then
    echo
    echo "==> Gateway unit tests"
    if (
      cd gateway
      OMERTA_GATEWAY_ADMIN_TOKEN="test-only-admin-token" \
        NODE_ENV="development" \
        npm exec -- vitest run --root .. tests/gateway
    ); then
      echo "PASSED: Gateway unit tests"
    else
      exit_code=$?
      echo "FAILED: Gateway unit tests (exit $exit_code)" >&2
      failures+=("Gateway unit tests")
    fi
  fi

  if [ -f "console/package.json" ]; then
    echo
    echo "==> Console unit tests"
    if (cd console && npm run test -- --config vitest.config.mts); then
      echo "PASSED: Console unit tests"
    else
      exit_code=$?
      echo "FAILED: Console unit tests (exit $exit_code)" >&2
      failures+=("Console unit tests")
    fi
  fi
else
  echo "npm not found; Node tests cannot run." >&2
  failures+=("Node tests")
fi

if command -v cargo >/dev/null 2>&1 && [ -f "runtime-daemon/Cargo.toml" ]; then
  run_check "Runtime manifest contract" bash -c \
    'cargo metadata --manifest-path runtime-daemon/Cargo.toml --no-deps --format-version 1 >/dev/null'
fi

if [ "${#failures[@]}" -gt 0 ]; then
  printf '\nTargeted test failures: %s\n' "${failures[*]}" >&2
  exit 1
fi

echo
echo "All targeted OMERTAOS tests passed."
