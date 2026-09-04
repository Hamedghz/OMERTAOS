"""Validate N3 database credentials and service DSN parity without printing secrets."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

if os.name == "posix":
    import grp
else:  # pragma: no cover - Linux ownership validation is exercised on target hosts.
    grp = None  # type: ignore[assignment]

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate import PLACEHOLDERS, _effective_values, parse_env


IDENTIFIER = re.compile(r"^[a-z_][a-z0-9_]*$")
CONTRACT = json.loads(
    (Path(__file__).resolve().parent / "contract.json").read_text(encoding="utf-8")
)


def _check_permissions(path: Path, mode: int, group: str | None, errors: list[str]) -> None:
    if os.name != "posix":
        return
    info = path.stat()
    actual_mode = stat.S_IMODE(info.st_mode)
    if info.st_uid != 0:
        errors.append(f"{path.name}: owner must be root")
    if actual_mode != mode:
        errors.append(f"{path.name}: mode must be {mode:04o}")
    if group is not None:
        assert grp is not None
        try:
            actual_group = grp.getgrgid(info.st_gid).gr_name
        except KeyError:
            actual_group = str(info.st_gid)
        if actual_group != group:
            errors.append(f"{path.name}: group must be {group}")


def _postgres_parts(raw: str, key: str, errors: list[str]) -> tuple[str, str, str] | None:
    parsed = urlparse(raw)
    if parsed.scheme not in {"postgres", "postgresql"}:
        errors.append(f"{key}: expected a PostgreSQL URL")
        return None
    if parsed.hostname != "127.0.0.1" or (parsed.port or 5432) != 5432:
        errors.append(f"{key}: Native PostgreSQL must use 127.0.0.1:5432")
    username = unquote(parsed.username or "")
    password = unquote(parsed.password or "")
    database = parsed.path.removeprefix("/")
    if not all((username, password, database)):
        errors.append(f"{key}: username, password, and database are required")
        return None
    return username, password, database


def validate_data_environment(
    installer_path: Path,
    control_path: Path,
    console_path: Path,
    *,
    examples: bool = False,
    check_permissions: bool = True,
) -> list[str]:
    errors: list[str] = []
    try:
        installer = parse_env(installer_path)
        control = parse_env(control_path)
        console = parse_env(console_path)
    except (OSError, ValueError) as exc:
        return [str(exc)]

    control, alias_errors = _effective_values(
        control,
        CONTRACT["deprecated_aliases"],
        allow_legacy=not examples,
    )
    errors.extend(f"{control_path.name}: {error}" for error in alias_errors)

    required = {
        "OMERTAOS_POSTGRES_ROLE",
        "OMERTAOS_POSTGRES_DATABASE",
        "OMERTAOS_POSTGRES_PASSWORD",
        "OMERTAOS_CONSOLE_POSTGRES_ROLE",
        "OMERTAOS_CONSOLE_POSTGRES_DATABASE",
        "OMERTAOS_CONSOLE_POSTGRES_PASSWORD",
    }
    missing = sorted(required - set(installer))
    if missing:
        errors.append(f"{installer_path.name}: missing keys {', '.join(missing)}")
        return errors

    role = installer["OMERTAOS_POSTGRES_ROLE"]
    database = installer["OMERTAOS_POSTGRES_DATABASE"]
    password = installer["OMERTAOS_POSTGRES_PASSWORD"]
    console_role = installer["OMERTAOS_CONSOLE_POSTGRES_ROLE"]
    console_database = installer["OMERTAOS_CONSOLE_POSTGRES_DATABASE"]
    console_password = installer["OMERTAOS_CONSOLE_POSTGRES_PASSWORD"]

    for key, value in (("OMERTAOS_POSTGRES_ROLE", role), ("OMERTAOS_POSTGRES_DATABASE", database),
                       ("OMERTAOS_CONSOLE_POSTGRES_ROLE", console_role),
                       ("OMERTAOS_CONSOLE_POSTGRES_DATABASE", console_database)):
        if not IDENTIFIER.fullmatch(value):
            errors.append(f"{key}: unsafe PostgreSQL identifier")
    if role == console_role or database == console_database:
        errors.append("Control and Console must use distinct PostgreSQL roles and databases")

    if examples:
        for key, value in (("OMERTAOS_POSTGRES_PASSWORD", password),
                           ("OMERTAOS_CONSOLE_POSTGRES_PASSWORD", console_password)):
            if value not in PLACEHOLDERS:
                errors.append(f"{key}: committed example must contain only a placeholder")
    else:
        for key, value in (("OMERTAOS_POSTGRES_PASSWORD", password),
                           ("OMERTAOS_CONSOLE_POSTGRES_PASSWORD", console_password)):
            if value in PLACEHOLDERS or len(value) < 16:
                errors.append(f"{key}: a non-placeholder secret of at least 16 characters is required")
        if password == console_password:
            errors.append("Control and Console PostgreSQL passwords must be distinct")

    control_parts = _postgres_parts(control.get("OMERTA_CONTROL_POSTGRES_DSN", ""),
                                    "OMERTA_CONTROL_POSTGRES_DSN", errors)
    console_parts = _postgres_parts(console.get("DATABASE_URL", ""), "DATABASE_URL", errors)
    if control_parts and control_parts != (role, password, database):
        errors.append("Control PostgreSQL DSN does not match installer credentials")
    if console_parts and console_parts != (console_role, console_password, console_database):
        errors.append("Console PostgreSQL DSN does not match installer credentials")

    redis = urlparse(control.get("OMERTA_CONTROL_REDIS_URL", ""))
    if redis.scheme != "redis" or redis.hostname != "127.0.0.1" or (redis.port or 6379) != 6379:
        errors.append("OMERTA_CONTROL_REDIS_URL: Native Redis must use 127.0.0.1:6379")

    if not examples and check_permissions:
        _check_permissions(installer_path, 0o600, None, errors)
        _check_permissions(control_path, 0o640, "omertaos", errors)
        _check_permissions(console_path, 0o640, "omertaos", errors)
    return errors


def main() -> int:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--installer", type=Path, default=Path("/etc/omertaos/installer.env"))
    parser.add_argument("--control", type=Path, default=Path("/etc/omertaos/control.env"))
    parser.add_argument("--console", type=Path, default=Path("/etc/omertaos/console.env"))
    parser.add_argument("--examples", action="store_true")
    args = parser.parse_args()
    if args.examples:
        args.installer = root / "installer.env.example"
        args.control = root / "control.env.example"
        args.console = root / "console.env.example"
    errors = validate_data_environment(args.installer, args.control, args.console, examples=args.examples)
    if errors:
        print("Native data environment FAILED")
        for error in errors:
            print(f"- {error}")
        return 1
    print("Native data environment passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
