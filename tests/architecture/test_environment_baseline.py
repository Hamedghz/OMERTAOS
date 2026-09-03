from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def test_full_compose_uses_current_control_entrypoints_and_grpc_endpoint() -> None:
    compose = (REPO_ROOT / "deploy/docker/compose/full.yml").read_text(
        encoding="utf-8"
    )

    assert "control.os.healthcheck" not in compose
    assert "control.os.main" not in compose
    assert 'command: ["python", "-m", "control.app.serve"]' in compose
    assert "${AION_CONTROL_GRPC:-control:50051}" in compose
    assert "${AION_RATE_LIMIT_PER_IP:-30}" in compose


def test_active_environment_example_has_unambiguous_control_defaults() -> None:
    example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")

    assert example.count("AION_CONTROL_POSTGRES_DSN=") == 1
    assert "AION_CONTROL_GRPC=control:50051" in example
    assert "AION_RATE_LIMIT_PER_IP=30" in example


def test_makefile_maps_professional_gateway_profile_to_full_runtime_profile() -> None:
    makefile = (REPO_ROOT / "Makefile").read_text(encoding="utf-8")

    assert "AION_PROFILE=professional OMERTA_PROFILE=full" in makefile
