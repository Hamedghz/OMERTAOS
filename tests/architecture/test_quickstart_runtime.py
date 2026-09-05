from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_quickstart_uses_canonical_runtime_daemon() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()

    assert "  runtime:\n" in compose
    assert "image: ${OMERTA_RUNTIME_IMAGE:-${AION_RUNTIME_IMAGE:-omertaos-runtime}}" in compose
    assert "dockerfile: runtime-daemon/Dockerfile" in compose
    assert "OMERTA_RUNTIME_BIND_ADDR: 0.0.0.0:50051" in compose
    assert (
        "OMERTA_CONTROL_GRPC_BIND: "
        "${OMERTA_CONTROL_GRPC_BIND:-${AION_CONTROL_GRPC_BIND:-0.0.0.0:50051}}"
        in compose
    )
    assert (
        '"127.0.0.1:${OMERTA_RUNTIME_HOST_PORT:-'
        '${AION_RUNTIME_HOST_PORT:-50051}}:50051"' in compose
    )
    assert '["CMD", "/usr/local/bin/runtime-daemon", "--healthcheck"]' in compose
    assert "runtime:\n        condition: service_healthy" in compose
    assert "  kernel:\n" not in compose

    dockerfile = (REPO_ROOT / "runtime-daemon" / "Dockerfile").read_text()
    assert "ENV CARGO_BUILD_JOBS=1" in dockerfile


def test_quickstart_stages_runtime_lease_secret_for_non_root_runtime() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()
    runtime = compose.split("  runtime:\n", maxsplit=1)[1].split(
        "  control:\n", maxsplit=1
    )[0]

    assert "  runtime-lease-secret-init:\n" in compose
    assert "OMERTA_RUNTIME_LEASE_HMAC_KEY:" not in compose
    assert "OMERTA_RUNTIME_LEASE_HMAC_KEY_FILE: /run/secrets/runtime-lease-hmac-key" in runtime
    assert "chown 10001:10001" in compose
    assert "chmod 0400" in compose
    assert "runtime-lease-secret:/run/secrets:ro" in runtime
    assert "runtime-lease-secret-init:\n        condition: service_completed_successfully" in runtime


def test_quickstart_uses_canonical_runtime_lease_namespace() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()
    two_workers = (
        REPO_ROOT / "deploy/docker/compose/quickstart.two-workers.yml"
    ).read_text()

    assert "AION_RUNTIME_LEASE_STATE_PATH" not in compose
    assert "AION_RUNTIME_LEASE_STATE_PATH" not in two_workers
    assert "OMERTA_RUNTIME_LEASE_TTL_SECONDS" in compose
    assert "OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS" in compose
    assert "OMERTA_RUNTIME_LEASE_STATE_PATH" in compose
    assert (
        "${OMERTA_RUNTIME_LEASE_TTL_SECONDS:-"
        "${AION_RUNTIME_LEASE_TTL_SECONDS:-45}}" in compose
    )
    assert (
        "${OMERTA_RUNTIME_LEASE_MAX_TTL_SECONDS:-"
        "${AION_RUNTIME_LEASE_MAX_TTL_SECONDS:-120}}" in compose
    )


def test_runtime_daemon_handles_container_stop_gracefully() -> None:
    server = (REPO_ROOT / "runtime-daemon" / "src" / "server.rs").read_text()

    assert ".serve_with_shutdown(addr, shutdown_signal())" in server
    assert "SignalKind::terminate()" in server


def test_quickstart_gateway_declares_development_api_key_map() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()

    assert (
        "OMERTA_GATEWAY_API_KEYS: "
        "${OMERTA_GATEWAY_API_KEYS:-${AION_GATEWAY_API_KEYS:-dev-admin-token:admin}}"
        in compose
    )


def test_quickstart_applies_console_migrations_before_control() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()
    control = compose.split("  control:\n", maxsplit=1)[1].split(
        "  gateway:\n", maxsplit=1
    )[0]

    assert "      install:\n        condition: service_completed_successfully" in control


def test_gateway_image_uses_locked_audited_dependency_install() -> None:
    dockerfile_bytes = (REPO_ROOT / "gateway" / "Dockerfile").read_bytes()

    assert not dockerfile_bytes.startswith(b"\xef\xbb\xbf")

    dockerfile = dockerfile_bytes.decode("utf-8")
    assert (
        "RUN --mount=type=cache,target=/root/.npm,sharing=locked npm ci"
        in dockerfile
    )
    assert "npm install" not in dockerfile
    assert "--no-audit" not in dockerfile


def test_control_image_includes_the_model_client_http_dependency() -> None:
    requirements = (REPO_ROOT / "control/requirements.docker.txt").read_text()

    assert "requests==2.32.5" in requirements.splitlines()


def test_console_image_uses_locked_reusable_dependency_install() -> None:
    dockerfile = (REPO_ROOT / "console" / "Dockerfile").read_text()

    assert "target=/pnpm/store,sharing=locked" in dockerfile
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "--network-concurrency=4 --child-concurrency=2" in dockerfile
    assert "--no-verify-store-integrity" not in dockerfile


def test_quickstart_supports_an_isolated_local_stack() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()

    assert (
        '"127.0.0.1:${OMERTA_CONTROL_HOST_PORT:-'
        '${AION_CONTROL_HOST_PORT:-8000}}:8000"' in compose
    )
    assert (
        '"${OMERTA_GATEWAY_HOST_PORT:-${AION_GATEWAY_HOST_PORT:-8080}}:8080"'
        in compose
    )
    assert (
        '"${OMERTA_CONSOLE_HOST_PORT:-${AION_CONSOLE_HOST_PORT:-3000}}:3000"'
        in compose
    )
    assert (
        "image: ${OMERTA_CONSOLE_IMAGE:-${AION_CONSOLE_IMAGE:-omertaos-console}}"
        in compose
    )
    assert (
        "OMERTA_CORS_ORIGINS: "
        "${OMERTA_CORS_ORIGINS:-${AION_CORS_ORIGINS:-http://localhost:3000}}"
        in compose
    )
    assert "NEXTAUTH_URL: ${NEXTAUTH_URL:-http://localhost:3000}" in compose
    assert "INTERNAL_CONSOLE_URL: http://localhost:3000" in compose
    assert (
        "NEXT_PUBLIC_GATEWAY_URL: "
        "${NEXT_PUBLIC_GATEWAY_URL:-http://localhost:8080}" in compose
    )
    assert (
        "name: ${OMERTA_DOCKER_NETWORK:-${AION_DOCKER_NETWORK:-omerta-net}}"
        in compose
    )
    qdrant = compose.split("  qdrant:\n", maxsplit=1)[1].split(
        "  minio:\n", maxsplit=1
    )[0]
    assert "qdrant-data:/qdrant/storage" in qdrant
    assert "GET /readyz HTTP/1.1" in qdrant
    assert "  qdrant-data:\n" in compose


def test_quickstart_enables_bounded_runtime_lifecycle_management() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/quickstart.yml").read_text()
    control = compose.split("  control:\n", maxsplit=1)[1].split(
        "  gateway:\n", maxsplit=1
    )[0]

    assert (
        "OMERTA_RUNTIME_AUTO_REGISTER: "
        "${OMERTA_RUNTIME_AUTO_REGISTER:-${AION_RUNTIME_AUTO_REGISTER:-true}}"
        in control
    )
    assert (
        "OMERTA_RUNTIME_NODE_ID: "
        "${OMERTA_RUNTIME_NODE_ID:-${AION_RUNTIME_NODE_ID:-runtime-quickstart-1}}"
        in control
    )
    assert (
        "OMERTA_RUNTIME_CAPABILITIES: "
        "${OMERTA_RUNTIME_CAPABILITIES:-${AION_RUNTIME_CAPABILITIES:-terminal.execute}}"
        in control
    )
    assert (
        "OMERTA_RUNTIME_HEARTBEAT_INTERVAL_SECONDS: "
        "${OMERTA_RUNTIME_HEARTBEAT_INTERVAL_SECONDS:-"
        "${AION_RUNTIME_HEARTBEAT_INTERVAL_SECONDS:-10}}" in control
    )
    assert (
        "OMERTA_RUNTIME_MANAGED_NODE_LIMIT: ${OMERTA_RUNTIME_MANAGED_NODE_LIMIT:-"
        "${AION_RUNTIME_MANAGED_NODE_LIMIT:-2}}"
        in control
    )


def test_two_worker_override_reuses_runtime_image_without_host_exposure() -> None:
    override = (
        REPO_ROOT / "deploy/docker/compose/quickstart.two-workers.yml"
    ).read_text()

    assert "  runtime-secondary:\n" in override
    assert (
        "image: ${OMERTA_RUNTIME_IMAGE:-${AION_RUNTIME_IMAGE:-omertaos-runtime}}"
        in override
    )
    assert "ports: []" in override
    assert '"endpoint":"runtime:50051"' in override
    assert '"endpoint":"runtime-secondary:50051"' in override
    assert '"tenant-shared","tenant-primary"' in override
    assert '"tenant-shared","tenant-secondary"' in override


def test_gateway_handles_container_stop_gracefully() -> None:
    server = (REPO_ROOT / "gateway" / "src" / "server.ts").read_text()

    assert "process.once('SIGTERM'" in server
    assert "await app.close()" in server
    assert "await closeRedis()" in server
