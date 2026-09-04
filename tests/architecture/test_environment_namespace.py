from __future__ import annotations

import json
import re
import shutil
import subprocess  # nosec B404 - invokes only the resolved local Python executable
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
INVENTORY_PATH = REPO_ROOT / "docs/migration/aion-env-inventory.json"
ORIGIN_NAMES_PATH = REPO_ROOT / "tests/architecture/fixtures/aion_env_origin_names.json"
CANONICAL_WRITERS = (
    ".env.example",
    "dev.env",
    "deploy/docker/compose/full.yml",
    "deploy/docker/compose/local.yml",
    "deploy/docker/compose/quickstart.two-workers.yml",
    "deploy/docker/compose/quickstart.yml",
)
LEGACY_ASSIGNMENT = re.compile(
    r"^\s*(?:-\s*)?AION_[A-Z0-9_]+\s*[:=]",
    re.MULTILINE,
)


def test_environment_namespace_inventory_is_current_and_has_no_new_legacy_readers() -> None:
    python = shutil.which("python") or shutil.which("python3") or sys.executable
    result = subprocess.run(  # nosec B603 - fixed local script and arguments
        [python, "scripts/audit_environment_namespace.py", "--check"],
        cwd=REPO_ROOT,
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr or result.stdout


def test_environment_namespace_inventory_preserves_m0_decisions() -> None:
    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    origin_names = json.loads(ORIGIN_NAMES_PATH.read_text(encoding="utf-8"))["names"]
    entries = {entry["legacy_name"]: entry for entry in inventory["entries"]}

    assert inventory["origin"] == {
        "commit": "a8c9b14b9f41dda49e7255fed0906472585acfbf",
        "captured_on": "2026-09-04",
        "scope": "tracked repository excluding historical migration evidence",
        "token_count": 164,
        "files_with_tokens": 99,
        "occurrences": 926,
    }
    assert inventory["snapshot"]["token_count"] == 164
    assert set(entries) == set(origin_names)
    assert entries["AION_PROFILE"]["canonical_name"] == "OMERTA_GATEWAY_PROFILE"
    assert entries["AION_VAULT_TOKEN"]["canonical_name"] == "VAULT_TOKEN"
    assert entries["AION_RUNTIME_LEASE_HMAC_KEY"]["legacy_alias"] is None
    assert entries["AION_RUNTIME_LEASE_V1"]["classification"] == "protocol-domain"
    assert entries["AION_CONTROL_"]["classification"] == "prefix-pattern"


def test_typescript_resolvers_stay_aligned_across_independent_builds() -> None:
    gateway_resolver = REPO_ROOT / "gateway/src/config/environment.ts"
    console_resolver = REPO_ROOT / "console/lib/environment.ts"

    assert gateway_resolver.read_bytes() == console_resolver.read_bytes()


def test_active_deployment_writers_only_inject_canonical_names() -> None:
    violations: list[str] = []
    for relative_path in CANONICAL_WRITERS:
        source = (REPO_ROOT / relative_path).read_text(encoding="utf-8")
        if LEGACY_ASSIGNMENT.search(source):
            violations.append(relative_path)

    assert not violations, f"legacy AION assignments remain in: {violations}"
