from __future__ import annotations

import pytest

from shared.config.environment import (
    DeprecatedEnvironmentAliasWarning,
    EnvironmentConflictError,
    EnvironmentValueError,
    integer_parser,
    resolve_environment,
)


CANONICAL = "OMERTA_TEST_CANONICAL"
LEGACY = "AION_TEST_LEGACY"


def test_resolver_accepts_new_only_old_only_and_equal_values() -> None:
    assert (
        resolve_environment(CANONICAL, aliases=(LEGACY,), environ={CANONICAL: "new"})
        == "new"
    )

    with pytest.warns(DeprecatedEnvironmentAliasWarning, match=LEGACY) as warnings:
        assert (
            resolve_environment(CANONICAL, aliases=(LEGACY,), environ={LEGACY: "old"})
            == "old"
        )
    assert "old" not in str(warnings[0].message)

    assert (
        resolve_environment(
            CANONICAL,
            aliases=(LEGACY,),
            environ={CANONICAL: "equal", LEGACY: "equal"},
        )
        == "equal"
    )


def test_resolver_rejects_conflicts_without_exposing_values() -> None:
    with pytest.raises(EnvironmentConflictError) as raised:
        resolve_environment(
            CANONICAL,
            aliases=(LEGACY,),
            environ={CANONICAL: "canonical-secret", LEGACY: "legacy-secret"},
        )

    rendered = f"{raised.value!s} {raised.value!r}"
    assert CANONICAL in rendered
    assert LEGACY in rendered
    assert "canonical-secret" not in rendered
    assert "legacy-secret" not in rendered


def test_resolver_applies_explicit_unset_and_blank_policies() -> None:
    assert resolve_environment(CANONICAL, default="fallback", environ={}) == "fallback"
    assert resolve_environment(CANONICAL, environ={}) is None
    assert (
        resolve_environment(CANONICAL, default="fallback", environ={CANONICAL: ""})
        == "fallback"
    )
    assert (
        resolve_environment(CANONICAL, blank="preserve", environ={CANONICAL: ""}) == ""
    )

    with pytest.raises(EnvironmentValueError, match=CANONICAL):
        resolve_environment(CANONICAL, blank="reject", environ={CANONICAL: ""})
    with pytest.raises(EnvironmentValueError, match="required"):
        resolve_environment(CANONICAL, required=True, environ={})


def test_typed_resolver_rejects_malformed_values_without_echoing_them() -> None:
    malformed = "not-a-number-sensitive"

    with pytest.raises(EnvironmentValueError) as raised:
        resolve_environment(
            CANONICAL,
            parser=integer_parser(minimum=8, maximum=32),
            environ={CANONICAL: malformed},
        )

    assert CANONICAL in str(raised.value)
    assert malformed not in f"{raised.value!s} {raised.value!r}"


@pytest.mark.parametrize("value", ["7", "33"])
def test_typed_resolver_enforces_bounds(value: str) -> None:
    with pytest.raises(EnvironmentValueError, match=CANONICAL):
        resolve_environment(
            CANONICAL,
            parser=integer_parser(minimum=8, maximum=32),
            environ={CANONICAL: value},
        )
