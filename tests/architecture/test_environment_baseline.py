from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_full_compose_uses_current_control_entrypoints_and_grpc_endpoint() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/full.yml").read_text(
        encoding="utf-8"
    )

    assert "control.os.healthcheck" not in compose
    assert "control.os.main" not in compose
    assert 'command: ["python", "-m", "control.app.serve"]' in compose
    assert "${OMERTA_CONTROL_GRPC:-${AION_CONTROL_GRPC:-control:50051}}" in compose
    assert "${OMERTA_RATE_LIMIT_PER_IP:-${AION_RATE_LIMIT_PER_IP:-30}}" in compose


def test_active_environment_example_has_unambiguous_control_defaults() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    assert example.count("OMERTA_CONTROL_POSTGRES_DSN=") == 1
    assert "AION_CONTROL_POSTGRES_DSN=" not in example
    assert "OMERTA_CONTROL_GRPC=control:50051" in example
    assert "OMERTA_RATE_LIMIT_PER_IP=30" in example


def test_makefile_maps_professional_gateway_profile_to_full_runtime_profile() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "OMERTA_GATEWAY_PROFILE=professional OMERTA_PROFILE=full" in makefile


def test_environment_schema_v2_publishes_canonical_names_and_deprecated_aliases() -> None:
    schema = json.loads((REPO_ROOT / ".env.schema").read_text(encoding="utf-8"))

    assert schema["schema"] == "env-schema/v2"
    variables = schema["variables"]
    assert variables
    assert all(not variable["name"].startswith("AION_") for variable in variables)
    assert any(
        "AION_GATEWAY_PORT" in variable.get("deprecated_aliases", [])
        for variable in variables
        if variable["name"] == "OMERTA_GATEWAY_PORT"
    )


def test_docker_installer_migrates_env_without_printing_or_deleting_secrets() -> None:
    installer = (REPO_ROOT / "deploy/docker/scripts/install.sh").read_text(
        encoding="utf-8"
    )

    assert "--migrate-env-file .env" in installer
    assert "--reject-legacy-secrets" in installer
    assert 'chmod 0600 .env' in installer
    assert 'set_env "OMERTA_GATEWAY_ADMIN_TOKEN"' in installer
    assert 'set_env "AION_' not in installer
    assert "down -v" not in installer
    assert "Password:" not in installer
    assert "API key:" not in installer
