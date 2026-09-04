"""Canonical model-profile reader backed by ``registry/models``."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Any

import yaml

from shared.config.environment import resolve_environment

_FORBIDDEN_SECRET_KEYS = {
    "accesskey",
    "apikey",
    "password",
    "secret",
    "secretkey",
    "token",
}


def _find_embedded_secret(value: object, path: str = "profile") -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            normalized = str(key).lower().replace("_", "").replace("-", "")
            nested_path = f"{path}.{key}"
            if normalized in _FORBIDDEN_SECRET_KEYS and nested is not None and nested != "":
                return nested_path
            found = _find_embedded_secret(nested, nested_path)
            if found:
                return found
    elif isinstance(value, list):
        for index, nested in enumerate(value):
            found = _find_embedded_secret(nested, f"{path}[{index}]")
            if found:
                return found
    return None


@dataclass(frozen=True, slots=True)
class ModelProfile:
    name: str
    provider: str
    version: str
    source: Path
    metadata: dict[str, Any]

    @property
    def id(self) -> str:
        return f"{self.provider}/{self.name}@{self.version}"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, **self.metadata}


def default_models_directory() -> Path:
    configured = resolve_environment(
        "OMERTA_CONTROL_MODELS_DIRECTORY",
        aliases=("AION_CONTROL_MODELS_DIRECTORY",),
    )
    if configured:
        assert isinstance(configured, str)
        return Path(configured).expanduser().resolve()
    return Path(__file__).resolve().parents[2] / "registry" / "models"


class ModelRegistry:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).resolve() if root else default_models_directory()
        self._lock = RLock()
        self._profiles: dict[str, ModelProfile] = {}
        self.reload()

    def reload(self) -> None:
        profiles: dict[str, ModelProfile] = {}
        if self.root.exists():
            for path in sorted(self.root.rglob("*.yaml")):
                payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
                if not isinstance(payload, dict):
                    raise ValueError(f"model profile must be a mapping: {path}")
                embedded_secret = _find_embedded_secret(payload)
                if embedded_secret:
                    raise ValueError(f"model profile must reference secrets, not embed {embedded_secret}: {path}")
                name = payload.get("name") or payload.get("id")
                version = payload.get("version") or "legacy"
                missing = [key for key, value in (("name/id", name), ("provider", payload.get("provider"))) if not value]
                if missing:
                    raise ValueError(f"model profile {path} is missing: {', '.join(missing)}")
                normalized = dict(payload)
                normalized.setdefault("name", str(name))
                normalized.setdefault("version", str(version))
                normalized["schema_status"] = "versioned" if payload.get("version") else "legacy-unversioned"
                profile = ModelProfile(
                    name=str(name),
                    provider=str(payload["provider"]),
                    version=str(version),
                    source=path,
                    metadata=normalized,
                )
                if profile.id in profiles:
                    raise ValueError(f"duplicate model profile id: {profile.id}")
                profiles[profile.id] = profile
        with self._lock:
            self._profiles = profiles

    def list_models(self) -> list[dict[str, Any]]:
        with self._lock:
            return [self._profiles[key].to_dict() for key in sorted(self._profiles)]

    def get(self, profile_id: str) -> ModelProfile | None:
        with self._lock:
            return self._profiles.get(profile_id)


_MODEL_REGISTRY: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    global _MODEL_REGISTRY
    if _MODEL_REGISTRY is None:
        _MODEL_REGISTRY = ModelRegistry()
    return _MODEL_REGISTRY


__all__ = ["ModelProfile", "ModelRegistry", "default_models_directory", "get_model_registry"]
