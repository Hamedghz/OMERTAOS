from __future__ import annotations

import os
import warnings
from collections.abc import Callable, Mapping, Sequence
from typing import Literal, TypeVar, cast


T = TypeVar("T")
BlankPolicy = Literal["unset", "preserve", "reject"]
_MISSING = object()


class EnvironmentResolutionError(ValueError):
    """Base error for fail-closed environment resolution."""


class EnvironmentConflictError(EnvironmentResolutionError):
    """Raised when canonical and compatibility names disagree."""


class EnvironmentValueError(EnvironmentResolutionError):
    """Raised when a selected environment value is invalid."""


class DeprecatedEnvironmentAliasWarning(UserWarning):
    """Signals use of a legacy environment name without exposing its value."""


def _deprecated_alias_warning(canonical_name: str, legacy_name: str) -> None:
    warnings.warn(
        f"{legacy_name} is deprecated; use {canonical_name}",
        DeprecatedEnvironmentAliasWarning,
        stacklevel=3,
    )


def _normalize_value(name: str, value: str | None, blank: BlankPolicy) -> str | None:
    if value != "":
        return value
    if blank == "unset":
        return None
    if blank == "preserve":
        return value
    if blank == "reject":
        raise EnvironmentValueError(f"{name} may not be blank")
    raise ValueError(f"unsupported blank policy: {blank}")


def resolve_environment(
    canonical_name: str,
    *,
    aliases: Sequence[str] = (),
    default: str | object = _MISSING,
    required: bool = False,
    blank: BlankPolicy = "unset",
    parser: Callable[[str], T] | None = None,
    environ: Mapping[str, str] | None = None,
    on_deprecated: Callable[[str, str], None] = _deprecated_alias_warning,
) -> T | str | None:
    """Resolve one canonical setting and deprecated aliases without value leakage."""

    names = (canonical_name, *aliases)
    if not all(names) or len(set(names)) != len(names):
        raise ValueError("environment names must be non-empty and unique")
    if required and default is not _MISSING:
        raise ValueError("required environment settings cannot declare a default")
    if default is not _MISSING and not isinstance(default, str):
        raise TypeError("environment defaults must be strings")
    if blank not in {"unset", "preserve", "reject"}:
        raise ValueError(f"unsupported blank policy: {blank}")

    source = os.environ if environ is None else environ
    present: list[tuple[str, str]] = []
    for name in names:
        value = _normalize_value(name, source.get(name), blank)
        if value is not None:
            present.append((name, value))

    if present:
        distinct_values = {value for _, value in present}
        if len(distinct_values) > 1:
            conflicting_names = ", ".join(
                name for name, _ in present if name != canonical_name
            )
            raise EnvironmentConflictError(
                f"{canonical_name} conflicts with deprecated {conflicting_names}"
            )
        canonical = next(
            ((name, value) for name, value in present if name == canonical_name),
            None,
        )
        selected_name, raw_value = canonical or present[0]
        if canonical is None:
            for legacy_name, _ in present:
                on_deprecated(canonical_name, legacy_name)
    elif default is not _MISSING:
        selected_name = canonical_name
        raw_value = cast(str, default)
    elif required:
        raise EnvironmentValueError(f"{canonical_name} is required")
    else:
        return None

    if parser is None:
        return raw_value
    try:
        return parser(raw_value)
    except Exception:
        raise EnvironmentValueError(f"{selected_name} is invalid") from None


def integer_parser(
    *, minimum: int | None = None, maximum: int | None = None
) -> Callable[[str], int]:
    def parse(value: str) -> int:
        parsed = int(value)
        if minimum is not None and parsed < minimum:
            raise ValueError("below minimum")
        if maximum is not None and parsed > maximum:
            raise ValueError("above maximum")
        return parsed

    return parse
