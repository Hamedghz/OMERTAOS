"""Validate the N1 Native environment contract without loading any secrets."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse


PLACEHOLDERS = {"CHANGE_ME", "REPLACE_ME", "<REQUIRED>"}
LINE = re.compile(r"^[A-Z][A-Z0-9_]*=.*$")
SENSITIVE_VALUE = re.compile(r"(?i)(://[^:/@]+:)[^@/]+(@)")


def _safe_error(error: str) -> str:
    """Keep validation diagnostics useful without echoing credentials."""
    return SENSITIVE_VALUE.sub(r"\1<redacted>\2", error)


def parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if not LINE.fullmatch(line):
            raise ValueError(f"{path}:{number}: invalid EnvironmentFile assignment")
        key, value = line.split("=", 1)
        if key in values:
            raise ValueError(f"{path}:{number}: duplicate key {key}")
        if "${" in value or "$(" in value or "`" in value:
            raise ValueError(f"{path}:{number}: shell expansion is not allowed")
        values[key] = value
    return values


def _is_loopback(value: str) -> bool:
    host = value.rsplit(":", 1)[0] if ":" in value and "://" not in value else value
    if "://" in value:
        host = urlparse(value).hostname or ""
    return host in {"127.0.0.1", "localhost", "::1"}


def _effective_values(
    values: dict[str, str],
    aliases: dict[str, str],
    *,
    allow_legacy: bool,
) -> tuple[dict[str, str], list[str]]:
    effective = dict(values)
    errors: list[str] = []
    for legacy_name, canonical_name in aliases.items():
        legacy_value = values.get(legacy_name)
        canonical_value = values.get(canonical_name)
        if legacy_value is None:
            continue
        if not allow_legacy:
            errors.append(
                f"deprecated environment key {legacy_name}; use {canonical_name}"
            )
            continue
        if (
            legacy_value
            and canonical_value
            and legacy_value != canonical_value
        ):
            errors.append(
                f"conflicting environment aliases: {canonical_name}, {legacy_name}"
            )
            continue
        if not canonical_value:
            effective[canonical_name] = legacy_value
    return effective, errors


def validate_directory(env_dir: Path, *, strict: bool = False) -> list[str]:
    contract = json.loads((env_dir / "contract.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    parsed: dict[str, dict[str, str]] = {}
    aliases = contract.get("deprecated_aliases", {})
    if contract.get("version") != 2:
        errors.append("native environment contract version must be 2")

    for filename, rules in contract["templates"].items():
        path = env_dir / (filename.removesuffix(".example") if strict else filename)
        if not path.is_file():
            errors.append(f"missing {path.name}")
            continue
        try:
            values = parse_env(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        effective, alias_errors = _effective_values(
            values,
            aliases,
            allow_legacy=strict,
        )
        errors.extend(f"{path.name}: {error}" for error in alias_errors)
        parsed[filename] = effective
        missing = sorted(set(rules["required"]) - set(effective))
        if missing:
            errors.append(f"{path.name}: missing keys {', '.join(missing)}")
        for prefix in rules.get("forbidden_prefixes", []):
            hits = sorted(key for key in values if key.startswith(prefix))
            if hits:
                errors.append(f"{path.name}: forbidden boundary keys {', '.join(hits)}")

    combined = {key: value for values in parsed.values() for key, value in values.items()}
    for key in contract["secret_keys"]:
        occurrences = [values[key] for values in parsed.values() if key in values]
        if not occurrences:
            errors.append(f"secret contract key is absent: {key}")
        for value in occurrences:
            if strict and (value in PLACEHOLDERS or "CHANGE_ME" in value):
                errors.append(f"{key}: placeholder is forbidden in strict mode")
            if not strict and value not in PLACEHOLDERS:
                errors.append(f"{key}: example must contain only a placeholder")

    for key in contract.get("credential_url_keys", []):
        occurrences = [values[key] for values in parsed.values() if key in values]
        if not occurrences:
            errors.append(f"credential URL contract key is absent: {key}")
        for value in occurrences:
            password = urlparse(value).password
            if not password:
                errors.append(f"{key}: URL must contain an explicit credential placeholder")
            elif strict and password in PLACEHOLDERS:
                errors.append(f"{key}: credential placeholder is forbidden in strict mode")
            elif not strict and password not in PLACEHOLDERS:
                errors.append(f"{key}: example credential must be a placeholder")

    for key in contract["port_keys"]:
        if key not in combined:
            continue
        try:
            port = int(combined[key])
            if not 1 <= port <= 65535:
                raise ValueError
        except ValueError:
            errors.append(f"{key}: must be a valid TCP port")

    for key in contract["loopback_keys"]:
        value = combined.get(key)
        if value is not None and not _is_loopback(value):
            errors.append(f"{key}: Native internal boundary must be loopback-only")

    grpc = combined.get("OMERTA_CONTROL_GRPC", "")
    if "://" in grpc:
        errors.append("OMERTA_CONTROL_GRPC: expected host:port without URL scheme")

    for profile in contract["profiles"]:
        path = env_dir / "profiles" / f"{profile}.env"
        if not path.is_file():
            errors.append(f"missing profile {path.name}")
            continue
        try:
            values = parse_env(path)
        except ValueError as exc:
            errors.append(str(exc))
            continue
        if values.get("OMERTA_PROFILE") != profile:
            errors.append(f"{path.name}: OMERTA_PROFILE must be {profile}")
        expected_gateway_profile = contract["gateway_profiles"][profile]
        if values.get("OMERTA_GATEWAY_PROFILE") != expected_gateway_profile:
            errors.append(
                f"{path.name}: OMERTA_GATEWAY_PROFILE must be "
                f"{expected_gateway_profile}"
            )

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--strict", action="store_true", help="validate rendered files and reject placeholders")
    args = parser.parse_args()
    errors = validate_directory(args.directory.resolve(), strict=args.strict)
    if errors:
        print("Native environment contract FAILED")
        for error in errors:
            print(f"- {_safe_error(error)}")
        return 1
    print("Native environment contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
