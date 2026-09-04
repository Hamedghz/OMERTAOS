#!/usr/bin/env python3
"""Validate OMERTA environment aliases without exposing configuration values."""

from __future__ import annotations

import argparse
import ast
import json
import os
import re
import stat
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INVENTORY = REPO_ROOT / "docs/migration/aion-env-inventory.json"
ASSIGNMENT = re.compile(
    r"^(?:export[ \t]+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*=(?P<value>.*)$"
)


@dataclass(frozen=True)
class AliasGroup:
    canonical_name: str
    aliases: tuple[str, ...]
    secret: bool


@dataclass(frozen=True)
class ValidationResult:
    warnings: tuple[str, ...]
    errors: tuple[str, ...]


class EnvironmentFileError(ValueError):
    """Raised for malformed dotenv input without retaining its values."""


def load_alias_contract(
    inventory_path: Path = DEFAULT_INVENTORY,
) -> tuple[tuple[AliasGroup, ...], tuple[str, ...]]:
    payload = json.loads(inventory_path.read_text(encoding="utf-8"))
    grouped_aliases: dict[str, set[str]] = defaultdict(set)
    grouped_secret: dict[str, bool] = defaultdict(bool)
    unsupported_aliases: set[str] = set()

    for entry in payload["entries"]:
        canonical_name = entry.get("canonical_name")
        legacy_name = entry["legacy_name"]
        state = entry["migration_state"]
        if state == "migrated-no-alias":
            unsupported_aliases.add(legacy_name)
            continue
        if (
            not canonical_name
            or not entry.get("legacy_alias")
            or state in {"excluded", "quarantined-stale"}
        ):
            continue
        grouped_aliases[canonical_name].add(legacy_name)
        grouped_secret[canonical_name] |= bool(entry.get("secret"))

    groups = tuple(
        AliasGroup(
            canonical_name=canonical_name,
            aliases=tuple(sorted(aliases)),
            secret=grouped_secret[canonical_name],
        )
        for canonical_name, aliases in sorted(grouped_aliases.items())
    )
    return groups, tuple(sorted(unsupported_aliases))


def _normalize_dotenv_value(raw: str) -> str:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        try:
            parsed = ast.literal_eval(value)
        except (SyntaxError, ValueError):
            return value
        return parsed if isinstance(parsed, str) else value
    return value


def parse_environment_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise EnvironmentFileError(f"cannot read environment file: {path}") from exc

    for line_number, raw_line in enumerate(lines, 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = ASSIGNMENT.fullmatch(line)
        if match is None:
            raise EnvironmentFileError(
                f"{path}:{line_number}: invalid environment assignment"
            )
        name = match.group("name")
        if name in values:
            raise EnvironmentFileError(
                f"{path}:{line_number}: duplicate environment key {name}"
            )
        values[name] = _normalize_dotenv_value(match.group("value"))
    return values


def merged_environment(
    paths: Sequence[Path],
    *,
    process_environment: Mapping[str, str] | None,
) -> dict[str, str]:
    values: dict[str, str] = {}
    for path in paths:
        values.update(parse_environment_file(path))
    if process_environment is not None:
        values.update(process_environment)
    return values


def validate_environment_aliases(
    values: Mapping[str, str],
    groups: Sequence[AliasGroup],
    unsupported_aliases: Sequence[str] = (),
    *,
    reject_legacy_secrets: bool = False,
) -> ValidationResult:
    warnings: list[str] = []
    errors: list[str] = []

    for legacy_name in unsupported_aliases:
        if legacy_name in values:
            errors.append(
                f"unsupported legacy environment key {legacy_name}; no alias is permitted"
            )

    for group in groups:
        names = (group.canonical_name, *group.aliases)
        present = [(name, values[name]) for name in names if values.get(name)]
        if len({value for _, value in present}) > 1:
            errors.append(
                "conflicting environment aliases: "
                + ", ".join(name for name, _ in present)
            )
            continue
        if not present or any(name == group.canonical_name for name, _ in present):
            continue
        for legacy_name, _ in present:
            message = (
                f"deprecated environment alias {legacy_name}; "
                f"use {group.canonical_name}"
            )
            if group.secret and reject_legacy_secrets:
                errors.append(message + "; migrate this secret explicitly")
            else:
                warnings.append(message)

    return ValidationResult(tuple(warnings), tuple(errors))


def _atomic_write(path: Path, rendered: str, mode: int) -> None:
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary_name = temporary.name
            os.fchmod(temporary.fileno(), mode)
            temporary.write(rendered)
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_name, path)
        temporary_name = None
    except OSError as exc:
        raise EnvironmentFileError(f"cannot update environment file: {path}") from exc
    finally:
        if temporary_name is not None:
            Path(temporary_name).unlink(missing_ok=True)


def update_environment_file(path: Path, updates: Mapping[str, str]) -> None:
    """Apply validated key updates atomically while retaining unrelated lines."""

    if path.is_symlink():
        raise EnvironmentFileError(f"refusing to update symbolic link: {path}")
    parse_environment_file(path)
    for name, value in updates.items():
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name):
            raise EnvironmentFileError("invalid environment key")
        if "\n" in value or "\r" in value:
            raise EnvironmentFileError(f"environment value for {name} may not contain newlines")

    source = path.read_text(encoding="utf-8")
    remaining = dict(updates)
    output: list[str] = []
    for raw_line in source.splitlines(keepends=True):
        match = ASSIGNMENT.fullmatch(raw_line.rstrip("\r\n").strip())
        if match is None or match.group("name") not in remaining:
            output.append(raw_line)
            continue
        name = match.group("name")
        newline = (
            "\r\n"
            if raw_line.endswith("\r\n")
            else "\n"
            if raw_line.endswith("\n")
            else ""
        )
        output.append(f"{name}={remaining.pop(name)}{newline}")

    if remaining:
        if output and not output[-1].endswith(("\n", "\r")):
            output[-1] += "\n"
        output.extend(f"{name}={value}\n" for name, value in remaining.items())

    rendered = "".join(output)
    if rendered != source:
        _atomic_write(path, rendered, stat.S_IMODE(path.stat().st_mode))


def migrate_environment_file(
    path: Path,
    groups: Sequence[AliasGroup],
    unsupported_aliases: Sequence[str] = (),
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """Rewrite legacy aliases atomically without copying legacy-only secrets."""

    if path.is_symlink():
        raise EnvironmentFileError(f"refusing to migrate symbolic link: {path}")
    values = parse_environment_file(path)
    result = validate_environment_aliases(
        values,
        groups,
        unsupported_aliases,
        reject_legacy_secrets=True,
    )
    if result.errors:
        raise EnvironmentFileError("; ".join(result.errors))

    alias_groups = {
        alias: group for group in groups for alias in group.aliases
    }
    emitted = {
        group.canonical_name
        for group in groups
        if group.canonical_name in values
    }
    renamed: list[str] = []
    removed: list[str] = []
    output: list[str] = []
    source = path.read_text(encoding="utf-8")

    for raw_line in source.splitlines(keepends=True):
        match = ASSIGNMENT.fullmatch(raw_line.rstrip("\r\n").strip())
        if match is None:
            output.append(raw_line)
            continue
        legacy_name = match.group("name")
        group = alias_groups.get(legacy_name)
        if group is None:
            output.append(raw_line)
            continue
        if group.canonical_name in emitted:
            removed.append(legacy_name)
            continue

        prefix = "export " if raw_line.lstrip().startswith("export ") else ""
        indentation = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        value = match.group("value")
        newline = (
            "\r\n"
            if raw_line.endswith("\r\n")
            else "\n"
            if raw_line.endswith("\n")
            else ""
        )
        output.append(
            f"{indentation}{prefix}{group.canonical_name}={value}{newline}"
        )
        emitted.add(group.canonical_name)
        renamed.append(legacy_name)

    rendered = "".join(output)
    if rendered == source:
        return tuple(renamed), tuple(removed)

    _atomic_write(path, rendered, stat.S_IMODE(path.stat().st_mode))

    return tuple(renamed), tuple(removed)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", action="append", default=[], type=Path)
    parser.add_argument("--migrate-env-file", type=Path)
    parser.add_argument("--inventory", type=Path, default=DEFAULT_INVENTORY)
    parser.add_argument("--no-process-environment", action="store_true")
    parser.add_argument("--reject-legacy-secrets", action="store_true")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args()

    if args.migrate_env_file is not None and args.env_file:
        parser.error("--migrate-env-file cannot be combined with --env-file")

    try:
        groups, unsupported_aliases = load_alias_contract(args.inventory)
        if args.migrate_env_file is not None:
            renamed, removed = migrate_environment_file(
                args.migrate_env_file,
                groups,
                unsupported_aliases,
            )
            if not args.quiet:
                print(
                    "Environment alias migration passed: "
                    f"{len(renamed)} renamed, {len(removed)} redundant aliases removed"
                )
            return 0
        values = merged_environment(
            args.env_file,
            process_environment=None if args.no_process_environment else os.environ,
        )
    except (EnvironmentFileError, KeyError, json.JSONDecodeError, OSError) as exc:
        print(f"environment alias preflight failed: {exc}", file=sys.stderr)
        return 2

    result = validate_environment_aliases(
        values,
        groups,
        unsupported_aliases,
        reject_legacy_secrets=args.reject_legacy_secrets,
    )
    if not args.quiet:
        for warning in result.warnings:
            print(f"WARNING: {warning}", file=sys.stderr)
    if result.errors:
        for error in result.errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    if not args.quiet:
        print("Environment alias preflight passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
