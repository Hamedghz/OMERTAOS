#!/usr/bin/env python3
"""Build and validate the AION-to-OMERTA environment namespace inventory."""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess  # nosec B404 - invokes only the resolved local Git executable
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = REPO_ROOT / "docs/migration/aion-env-inventory.json"
ALLOWLIST_PATH = (
    REPO_ROOT / "tests/architecture/fixtures/aion_env_direct_readers.json"
)
BASELINE_COMMIT = "a8c9b14b9f41dda49e7255fed0906472585acfbf"
TOKEN_PATTERN = re.compile(r"\bAION_[A-Z0-9_]+\b")

EXCLUDED_PATHS = {
    INVENTORY_PATH.relative_to(REPO_ROOT).as_posix(),
    ALLOWLIST_PATH.relative_to(REPO_ROOT).as_posix(),
    "docs/migration/aion-env-prefix-to-omerta.md",
    "scripts/audit_environment_namespace.py",
    "tests/architecture/test_environment_namespace.py",
}
EXCLUDED_PREFIXES = ("docs/migration/evidence/",)

DIRECT_READER_PATTERNS = (
    (
        "typescript-dot",
        re.compile(r"process\.env\.(?P<name>AION_[A-Z0-9_]+)\b"),
    ),
    (
        "typescript-index",
        re.compile(
            r"process\.env\[\s*['\"](?P<name>AION_[A-Z0-9_]+)['\"]\s*\]"
        ),
    ),
    (
        "python-getenv",
        re.compile(r"os\.getenv\(\s*['\"](?P<name>AION_[A-Z0-9_]+)['\"]"),
    ),
    (
        "python-environ-get",
        re.compile(
            r"os\.environ\.get\(\s*['\"](?P<name>AION_[A-Z0-9_]+)['\"]"
        ),
    ),
    (
        "python-environ-index",
        re.compile(
            r"os\.environ\[\s*['\"](?P<name>AION_[A-Z0-9_]+)['\"]\s*\]"
        ),
    ),
    (
        "rust-var",
        re.compile(
            r"(?:std::)?env::var\(\s*\"(?P<name>AION_[A-Z0-9_]+)\""
        ),
    ),
    (
        "powershell-env",
        re.compile(r"\$env:(?P<name>AION_[A-Z0-9_]+)\b", re.IGNORECASE),
    ),
    (
        "shell-or-compose-expansion",
        re.compile(r"\$\{(?P<name>AION_[A-Z0-9_]+)(?=[:}?+\-])"),
    ),
)

VAULT_STANDARD_NAMES = {
    "AION_VAULT_ADDR": "VAULT_ADDR",
    "AION_VAULT_APPROLE_ROLE_ID": "VAULT_APPROLE_ROLE_ID",
    "AION_VAULT_APPROLE_SECRET_ID": "VAULT_APPROLE_SECRET_ID",
    "AION_VAULT_AUTH_METHOD": "VAULT_AUTH_METHOD",
    "AION_VAULT_ENABLED": "VAULT_ENABLED",
    "AION_VAULT_KV_MOUNT": "VAULT_KV_MOUNT",
    "AION_VAULT_NAMESPACE": "VAULT_NAMESPACE",
    "AION_VAULT_TOKEN": "VAULT_TOKEN",
}

CANONICAL_OVERRIDES = {
    "AION_ADMIN_TOKEN": "OMERTA_GATEWAY_ADMIN_TOKEN",
    "AION_ADMIN_TOKEN_SECRET_PATH": "OMERTA_GATEWAY_ADMIN_TOKEN_SECRET_PATH",
    "AION_GATEWAY_ADMIN_TOKEN": "OMERTA_GATEWAY_ADMIN_TOKEN",
    "AION_GATEWAY_ADMIN_TOKEN_SECRET_PATH": (
        "OMERTA_GATEWAY_ADMIN_TOKEN_SECRET_PATH"
    ),
    "AION_PROFILE": "OMERTA_GATEWAY_PROFILE",
    **VAULT_STANDARD_NAMES,
}

IMPLEMENTED_DUAL_READ = {
    "AION_RUNTIME_LEASE_MAX_TTL_SECONDS",
    "AION_RUNTIME_LEASE_STATE_PATH",
    "AION_RUNTIME_LEASE_TTL_SECONDS",
}

HOST_BOUNDARY_NAMES = {
    "AION_CONSOLE_HOST_PORT",
    "AION_CONSOLE_IMAGE",
    "AION_CONTROL_HOST_PORT",
    "AION_DOCKER_COMPOSE_FILE",
    "AION_DOCKER_NETWORK",
    "AION_GATEWAY_HOST_PORT",
    "AION_QUICKSTART_COMPOSE_FILE",
    "AION_RUNTIME_HOST_PORT",
    "AION_RUNTIME_IMAGE",
}

SECRET_FRAGMENTS = (
    "ADMIN_TOKEN",
    "API_KEYS",
    "APPROLE_SECRET_ID",
    "HMAC_KEY",
    "JWT_SECRET",
    "LOCAL_SECRET_KEY",
    "PASSWORD",
    "SECRET_KEY",
    "TLS_KEY",
    "VAULT_KEY",
    "VAULT_TOKEN",
)

BOOLEAN_NAMES = {
    "AION_CONTROL_DISABLE_SECRETS",
    "AION_CONTROL_MINIO_SECURE",
    "AION_DEV_BYPASS_AUTH",
    "AION_DISABLE_WORKERS",
    "AION_DOCKER",
    "AION_ENABLE_PRISMA",
    "AION_METRICS_ENABLED",
    "AION_NETWORK_PROXY_STATUS_PUBLIC",
    "AION_OTEL_ENABLED",
    "AION_RUNTIME_AUTO_REGISTER",
    "AION_SELF_EVOLVING_ENABLED",
    "AION_TELEMETRY_OPT_IN",
    "AION_TLS_REQUIRED",
    "AION_TLS_REQUIRE_MTLS",
    "AION_TRUST_PROXY",
    "AION_VAULT_ENABLED",
}


def _git_tracked_paths(root: Path) -> tuple[str, ...]:
    git = shutil.which("git")
    if not git:
        raise RuntimeError("git executable is required")
    result = subprocess.run(  # nosec B603 - fixed Git subcommand and arguments
        [git, "ls-files", "-z"],
        cwd=root,
        check=True,
        capture_output=True,
    )
    return tuple(
        item.decode("utf-8").replace("\\", "/")
        for item in result.stdout.split(b"\0")
        if item
    )


def _is_scanned(path: str) -> bool:
    return path not in EXCLUDED_PATHS and not path.startswith(EXCLUDED_PREFIXES)


def _tracked_text(root: Path) -> Iterable[tuple[str, str]]:
    for relative_path in _git_tracked_paths(root):
        if not _is_scanned(relative_path):
            continue
        path = root / relative_path
        if not path.is_file():
            continue
        try:
            yield relative_path, path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue


def _owners(paths: Iterable[str]) -> list[str]:
    owners: set[str] = set()
    for path in paths:
        if path.startswith("deploy/docker/"):
            owners.add("docker-deployment")
        elif path.startswith("deploy/native/"):
            owners.add("native-deployment")
        elif path.startswith("deploy/kubernetes/"):
            owners.add("kubernetes-deployment")
        elif path.startswith(".github/") or path.startswith(".codex/"):
            owners.add("ci-tooling")
        elif path.startswith("tests/"):
            owners.add("tests")
        elif path.startswith("docs/"):
            owners.add("documentation")
        elif path in {".env.example", ".env.schema", "dev.env"}:
            owners.add("repository-configuration")
        elif path == "Makefile":
            owners.add("developer-tooling")
        elif "/" not in path:
            owners.add("repository-root")
        else:
            owners.add(path.split("/", maxsplit=1)[0])
    return sorted(owners)


def _canonical_name(name: str) -> str | None:
    if name.endswith("_"):
        return None
    if name.startswith("AION_TEST_"):
        return None
    return CANONICAL_OVERRIDES.get(name, "OMERTA_" + name.removeprefix("AION_"))


def _value_type(name: str) -> str:
    if name.endswith("_"):
        return "prefix-pattern"
    if name in BOOLEAN_NAMES:
        return "boolean"
    if name.endswith(("_PORT", "_TTL", "_SECONDS", "_MILLIS", "_MB", "_SIZE")):
        return "integer"
    if name.endswith("_JSON"):
        return "json"
    if name.endswith(("_URL", "_DSN", "_ENDPOINT", "_ADDR")):
        return "endpoint-or-url"
    if name.endswith(("_PATH", "_DIR", "_DIRECTORY", "_ROOT", "_FILE")):
        return "filesystem-path"
    if name.endswith(("_CAPABILITIES", "_TENANT_IDS", "_ROLES", "_ORIGINS")):
        return "delimited-list"
    return "string"


def _classification(name: str, paths: Iterable[str]) -> str:
    source_paths = tuple(paths)
    if name.endswith("_"):
        return "prefix-pattern"
    if name.startswith("AION_TEST_"):
        return "test-fixture"
    if name == "AION_RUNTIME_LEASE_V1":
        return "protocol-domain"
    if name in VAULT_STANDARD_NAMES:
        return "third-party-compatibility"
    if source_paths and all(path.startswith("docs/") for path in source_paths):
        return "documentation-reference"
    if name in {"AION_CONTROL_API", "AION_VAULT_KEY", "AION_VAULT_PROVIDER"}:
        return "stale-catalog-contract"
    return "product-environment"


def _migration_state(name: str) -> tuple[str, str]:
    if name.endswith("_"):
        return "excluded", "Prefix pattern, not a concrete environment key."
    if name.startswith("AION_TEST_"):
        return "excluded", "Synthetic test fixture, not an operator contract."
    if name == "AION_RUNTIME_LEASE_V1":
        return (
            "migrated-no-alias",
            "R6.15 accepted OMERTA_RUNTIME_LEASE_V1 before deployment.",
        )
    if name == "AION_RUNTIME_LEASE_HMAC_KEY":
        return (
            "migrated-no-alias",
            "R6.15 accepted the canonical HMAC key without a legacy alias.",
        )
    if name in IMPLEMENTED_DUAL_READ:
        return "dual-read-implemented", "Canonical and legacy conflicts fail closed."
    if name in VAULT_STANDARD_NAMES:
        return "pending-ecosystem-alias", "Canonical target is the standard VAULT namespace."
    if name in HOST_BOUNDARY_NAMES:
        return "pending-host-preflight", "Requires host-side conflict validation."
    if name == "AION_PROFILE":
        return (
            "mapping-decided",
            "Maps to OMERTA_GATEWAY_PROFILE; OMERTA_PROFILE is the Runtime edition profile.",
        )
    if name in {
        "AION_ADMIN_TOKEN",
        "AION_ADMIN_TOKEN_SECRET_PATH",
        "AION_GATEWAY_ADMIN_TOKEN",
        "AION_GATEWAY_ADMIN_TOKEN_SECRET_PATH",
    }:
        return (
            "mapping-decided",
            "Compatibility group maps to the Gateway internal-admin credential contract.",
        )
    if name in {"AION_CONTROL_API", "AION_VAULT_KEY", "AION_VAULT_PROVIDER"}:
        return "quarantined-stale", "Belongs to the non-canonical catalog Compose definition."
    return "pending-dual-read", "Preserve the current behavior until its owner migrates."


def _schema_contracts(root: Path) -> dict[str, dict[str, Any]]:
    payload = json.loads((root / ".env.schema").read_text(encoding="utf-8"))
    return {
        variable["name"]: variable
        for variable in payload.get("variables", [])
        if isinstance(variable, dict) and isinstance(variable.get("name"), str)
    }


def _entry(
    name: str,
    locations: dict[str, int],
    schema_contract: dict[str, Any] | None,
) -> dict[str, Any]:
    paths = sorted(locations)
    state, note = _migration_state(name)
    secret = any(fragment in name for fragment in SECRET_FRAGMENTS)
    if schema_contract is None:
        required: bool | str = "owner-defined"
        default_state = "owner-defined"
        contract_source = "owning-reader-or-deployment"
    else:
        required = bool(schema_contract.get("required", False))
        if "default" not in schema_contract:
            default_state = "none-declared"
        elif secret:
            default_state = "declared-redacted"
        else:
            default_state = "declared"
        contract_source = ".env.schema"
    return {
        "legacy_name": name,
        "canonical_name": _canonical_name(name),
        "classification": _classification(name, paths),
        "owners": _owners(paths),
        "value_type": _value_type(name),
        "required": required,
        "default_state": default_state,
        "contract_source": contract_source,
        "migration_contract": "preserve-existing-required-and-default-behavior",
        "secret": secret,
        "migration_state": state,
        "legacy_alias": name if state not in {"excluded", "migrated-no-alias"} else None,
        "source_files": paths,
        "occurrences": sum(locations.values()),
        "note": note,
    }


def build_inventory(root: Path = REPO_ROOT) -> dict[str, Any]:
    locations: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    scanned_files = 0
    for relative_path, source in _tracked_text(root):
        matches = list(TOKEN_PATTERN.finditer(source))
        if not matches:
            continue
        scanned_files += 1
        for match in matches:
            locations[match.group(0)][relative_path] += 1

    schema_contracts = _schema_contracts(root)
    entries = [
        _entry(name, locations[name], schema_contracts.get(name))
        for name in sorted(locations)
    ]
    return {
        "schema_version": 1,
        "origin": {
            "commit": BASELINE_COMMIT,
            "captured_on": "2026-09-04",
            "scope": "tracked repository excluding historical migration evidence",
            "token_count": 164,
            "files_with_tokens": 99,
            "occurrences": 926,
        },
        "snapshot": {
            "token_count": len(entries),
            "files_with_tokens": scanned_files,
            "occurrences": sum(entry["occurrences"] for entry in entries),
        },
        "policy": {
            "canonical_product_prefix": "OMERTA_",
            "conflict": "fail-closed-with-key-names-only",
            "secret_values": "never-recorded",
            "wire_and_storage_identifiers": "out-of-scope",
            "standard_ecosystem_names": "preserved",
        },
        "entries": entries,
    }


def scan_direct_readers(root: Path = REPO_ROOT) -> list[dict[str, str]]:
    readers: set[tuple[str, str, str]] = set()
    for relative_path, source in _tracked_text(root):
        for kind, pattern in DIRECT_READER_PATTERNS:
            for match in pattern.finditer(source):
                readers.add((relative_path, match.group("name").upper(), kind))
    return [
        {"path": path, "name": name, "kind": kind}
        for path, name, kind in sorted(readers)
    ]


def _json_text(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=False) + "\n"


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_json_text(payload), encoding="utf-8")


def _check_exact(path: Path, payload: Any) -> list[str]:
    if not path.exists():
        return [f"missing generated file: {path.relative_to(REPO_ROOT)}"]
    if path.read_text(encoding="utf-8") != _json_text(payload):
        return [
            f"stale generated file: {path.relative_to(REPO_ROOT)}; "
            "run scripts/audit_environment_namespace.py --write"
        ]
    return []


def _check_reader_allowlist(readers: list[dict[str, str]]) -> list[str]:
    if not ALLOWLIST_PATH.exists():
        return [f"missing reader allowlist: {ALLOWLIST_PATH.relative_to(REPO_ROOT)}"]
    allowed_payload = json.loads(ALLOWLIST_PATH.read_text(encoding="utf-8"))
    allowed = {
        (item["path"], item["name"], item["kind"])
        for item in allowed_payload["readers"]
    }
    actual = {(item["path"], item["name"], item["kind"]) for item in readers}
    additions = sorted(actual - allowed)
    return [
        f"new direct legacy reader: {path} -> {name} ({kind})"
        for path, name, kind in additions
    ]


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument(
        "--bootstrap-reader-allowlist",
        action="store_true",
        help="M0-only: replace the reviewed legacy direct-reader baseline",
    )
    args = parser.parse_args()

    inventory = build_inventory()
    readers = scan_direct_readers()
    if args.write:
        _write_json(INVENTORY_PATH, inventory)
        if args.bootstrap_reader_allowlist:
            _write_json(
                ALLOWLIST_PATH,
                {
                    "schema_version": 1,
                    "baseline_commit": BASELINE_COMMIT,
                    "policy": "grandfathered legacy readers; additions are forbidden",
                    "readers": readers,
                },
            )
        print(
            f"inventory: {inventory['snapshot']['token_count']} tokens, "
            f"{inventory['snapshot']['files_with_tokens']} files, "
            f"{inventory['snapshot']['occurrences']} occurrences"
        )
        return 0

    errors = _check_exact(INVENTORY_PATH, inventory)
    errors.extend(_check_reader_allowlist(readers))
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(
        f"environment namespace gate passed: "
        f"{inventory['snapshot']['token_count']} inventoried tokens; "
        f"{len(readers)} grandfathered direct readers"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
