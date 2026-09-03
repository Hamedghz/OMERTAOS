from __future__ import annotations

from pathlib import Path

import pytest

from scripts import validate_environment_aliases as PREFLIGHT


REPO_ROOT = Path(__file__).resolve().parents[2]


def _group(canonical_name: str):
    groups, _ = PREFLIGHT.load_alias_contract()
    return next(group for group in groups if group.canonical_name == canonical_name)


def test_inventory_groups_multiple_admin_aliases_and_standard_vault_names() -> None:
    admin = _group("OMERTA_GATEWAY_ADMIN_TOKEN")
    vault = _group("VAULT_TOKEN")

    assert admin.aliases == ("AION_ADMIN_TOKEN", "AION_GATEWAY_ADMIN_TOKEN")
    assert admin.secret is True
    assert vault.aliases == ("AION_VAULT_TOKEN",)


def test_preflight_accepts_canonical_legacy_and_equal_values() -> None:
    group = _group("OMERTA_GATEWAY_PORT")

    canonical = PREFLIGHT.validate_environment_aliases(
        {"OMERTA_GATEWAY_PORT": "8080"}, [group]
    )
    legacy = PREFLIGHT.validate_environment_aliases(
        {"AION_GATEWAY_PORT": "8080"}, [group]
    )
    equal = PREFLIGHT.validate_environment_aliases(
        {"OMERTA_GATEWAY_PORT": "8080", "AION_GATEWAY_PORT": "8080"},
        [group],
    )

    assert canonical == PREFLIGHT.ValidationResult((), ())
    assert legacy.errors == ()
    assert legacy.warnings == (
        "deprecated environment alias AION_GATEWAY_PORT; use OMERTA_GATEWAY_PORT",
    )
    assert equal == PREFLIGHT.ValidationResult((), ())


def test_preflight_fails_closed_without_exposing_conflicting_values() -> None:
    group = _group("OMERTA_GATEWAY_ADMIN_TOKEN")
    canonical_value = "canonical-sensitive-value"
    legacy_value = "legacy-sensitive-value"

    result = PREFLIGHT.validate_environment_aliases(
        {
            "OMERTA_GATEWAY_ADMIN_TOKEN": canonical_value,
            "AION_GATEWAY_ADMIN_TOKEN": legacy_value,
        },
        [group],
    )
    rendered = " ".join(result.errors)

    assert "OMERTA_GATEWAY_ADMIN_TOKEN" in rendered
    assert "AION_GATEWAY_ADMIN_TOKEN" in rendered
    assert canonical_value not in rendered
    assert legacy_value not in rendered


def test_preflight_can_require_explicit_secret_migration() -> None:
    group = _group("OMERTA_GATEWAY_ADMIN_TOKEN")
    result = PREFLIGHT.validate_environment_aliases(
        {"AION_GATEWAY_ADMIN_TOKEN": "legacy-sensitive-value"},
        [group],
        reject_legacy_secrets=True,
    )

    assert result.warnings == ()
    assert "migrate this secret explicitly" in result.errors[0]
    assert "legacy-sensitive-value" not in result.errors[0]


def test_preflight_rejects_legacy_names_without_compatibility_aliases() -> None:
    _, unsupported = PREFLIGHT.load_alias_contract()
    result = PREFLIGHT.validate_environment_aliases(
        {"AION_RUNTIME_LEASE_HMAC_KEY": "legacy-sensitive-value"},
        [],
        unsupported,
    )

    assert result.errors
    assert "AION_RUNTIME_LEASE_HMAC_KEY" in result.errors[0]
    assert "legacy-sensitive-value" not in result.errors[0]


def test_environment_file_parser_reports_names_but_not_values(tmp_path: Path) -> None:
    path = tmp_path / "migration.env"
    path.write_text(
        "OMERTA_GATEWAY_ADMIN_TOKEN=first-sensitive-value\n"
        "OMERTA_GATEWAY_ADMIN_TOKEN=second-sensitive-value\n",
        encoding="utf-8",
    )

    with pytest.raises(PREFLIGHT.EnvironmentFileError) as raised:
        PREFLIGHT.parse_environment_file(path)

    rendered = str(raised.value)
    assert "OMERTA_GATEWAY_ADMIN_TOKEN" in rendered
    assert "first-sensitive-value" not in rendered
    assert "second-sensitive-value" not in rendered
