"""Secret provider backed by HashiCorp Vault."""
from __future__ import annotations

from functools import lru_cache
from typing import Any, Dict, Mapping, Tuple

from shared.config.environment import resolve_environment

try:  # pragma: no cover - optional dependency at runtime
    import hvac  # type: ignore
except ModuleNotFoundError as exc:  # pragma: no cover - handled at runtime
    hvac = None  # type: ignore
    _IMPORT_ERROR = exc
else:
    _IMPORT_ERROR = None


class SecretProviderError(RuntimeError):
    """Raised when the secret provider cannot fulfil a request."""


class SecretProvider:
    """Wrapper around the hvac client with simplified helpers."""

    def __init__(
        self,
        *,
        vault_addr: str | None = None,
        auth_method: str | None = None,
        namespace: str | None = None,
        kv_mount: str | None = None,
    ) -> None:
        if hvac is None:  # pragma: no cover - dependent on packaging
            message = (
                "HashiCorp Vault support requires the optional 'hvac' dependency. "
                "Install it (e.g. 'pip install hvac' or the 'control' extras) or "
                "set OMERTA_CONTROL_DISABLE_SECRETS=1 to disable Vault integration."
            )
            raise SecretProviderError(message) from _IMPORT_ERROR
        resolved_addr = vault_addr or resolve_environment(
            "VAULT_ADDR", aliases=("AION_VAULT_ADDR",), default=""
        )
        assert isinstance(resolved_addr, str)
        self._url = resolved_addr.strip()
        if not self._url:
            raise SecretProviderError("VAULT_ADDR must be set to contact Vault")

        resolved_auth_method = auth_method or resolve_environment(
            "VAULT_AUTH_METHOD", aliases=("AION_VAULT_AUTH_METHOD",), default="token"
        )
        resolved_namespace = namespace or resolve_environment(
            "VAULT_NAMESPACE", aliases=("AION_VAULT_NAMESPACE",)
        )
        resolved_kv_mount = kv_mount or resolve_environment(
            "VAULT_KV_MOUNT", aliases=("AION_VAULT_KV_MOUNT",), default="secret"
        )
        assert isinstance(resolved_auth_method, str)
        assert resolved_namespace is None or isinstance(resolved_namespace, str)
        assert isinstance(resolved_kv_mount, str)
        self._auth_method = resolved_auth_method.lower()
        self._namespace = resolved_namespace
        self._kv_mount = resolved_kv_mount.strip().strip("/")
        self._client = hvac.Client(url=self._url, namespace=self._namespace)
        self._token: str | None = None
        self._authenticate()

    # ------------------------------------------------------------------
    # Authentication helpers
    # ------------------------------------------------------------------
    def _authenticate(self) -> None:
        if self._auth_method == "token":
            token = resolve_environment(
                "VAULT_TOKEN",
                aliases=("AION_VAULT_TOKEN",),
            )
            if not token:
                raise SecretProviderError("VAULT_TOKEN must be set when using token auth")
            self._client.token = token
            self._token = token
        elif self._auth_method == "approle":
            role_id = resolve_environment(
                "VAULT_APPROLE_ROLE_ID",
                aliases=("AION_VAULT_APPROLE_ROLE_ID",),
            )
            secret_id = resolve_environment(
                "VAULT_APPROLE_SECRET_ID",
                aliases=("AION_VAULT_APPROLE_SECRET_ID",),
            )
            if not role_id or not secret_id:
                raise SecretProviderError(
                    "VAULT_APPROLE_ROLE_ID and VAULT_APPROLE_SECRET_ID are required for approle auth"
                )
            response = self._client.auth.approle.login(role_id=role_id, secret_id=secret_id)
            token = response.get("auth", {}).get("client_token")
            if not token:
                raise SecretProviderError("Failed to obtain Vault token via AppRole")
            self._client.token = token
            self._token = token
        else:
            raise SecretProviderError(f"Unsupported VAULT_AUTH_METHOD '{self._auth_method}'")

    # ------------------------------------------------------------------
    # Secret helpers
    # ------------------------------------------------------------------
    def get_secret(self, path: str) -> Dict[str, Any] | str:
        """Return the secret payload stored at *path*.

        The path may include the mount point (e.g. ``kv/data/aion/db-main``) or just the
        logical KV path (``aion/db-main``). When a KV-v2 mount is used we automatically
        normalise the mount/data prefixes.
        """

        mount_point, secret_path = self._split_mount_and_path(path)
        try:
            result = self._client.secrets.kv.v2.read_secret_version(
                path=secret_path,
                mount_point=mount_point,
            )
        except hvac.exceptions.InvalidPath:
            raise SecretProviderError(f"Secret not found at '{path}'") from None
        except Exception as exc:  # pragma: no cover - surface hvac errors
            raise SecretProviderError(f"Failed to read secret '{path}': {exc}") from exc

        data = result.get("data", {}).get("data")
        if data is None:
            raise SecretProviderError(f"Secret response for '{path}' was empty")
        if isinstance(data, Mapping):
            materialised = dict(data)
            if len(materialised) == 1 and "value" in materialised:
                value = materialised["value"]
                if isinstance(value, str):
                    return value
            return materialised
        raise SecretProviderError(f"Unexpected payload type for secret '{path}'")

    # ------------------------------------------------------------------
    def _split_mount_and_path(self, path: str) -> Tuple[str, str]:
        cleaned = path.strip().strip("/")
        if not cleaned:
            raise SecretProviderError("Secret path must not be empty")
        segments = cleaned.split("/")
        if len(segments) == 1:
            return self._kv_mount or "secret", segments[0]
        mount = segments[0]
        if len(segments) >= 3 and segments[1] == "data":
            return mount, "/".join(segments[2:])
        return mount, "/".join(segments[1:])


@lru_cache(maxsize=1)
def get_secret_provider() -> SecretProvider:
    """Return a cached :class:`SecretProvider` instance configured from env vars."""

    return SecretProvider()
