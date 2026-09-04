from __future__ import annotations

import base64
import json
import logging
import secrets
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import desc, select
from sqlalchemy.orm import Session
from Crypto.Cipher import AES  # nosec B413

from shared.config.environment import resolve_environment
from shared.secret_store.provider import SecretProviderError, get_secret_provider
from shared.telemetry.audit import emit_audit

from .healthcheck import test_profile
from .models import ProxyProfile
from .schemas import ProxyProfileCreate, ProxyProfileOut, ProxyProfileUpdate, ProxySecrets

LOGGER = logging.getLogger(__name__)
SENSITIVE_FIELDS = ("uuid", "password", "private_key", "public_key", "short_id")


class LocalSecretProvider:
    def __init__(self) -> None:
        configured_root = resolve_environment(
            "OMERTA_CONTROL_SECRET_DIR",
            aliases=("AION_CONTROL_SECRET_DIR",),
            default=".aion/secrets",
        )
        assert isinstance(configured_root, str)
        root = Path(configured_root)
        root.mkdir(parents=True, exist_ok=True)
        self.root = root
        raw_key = resolve_environment(
            "OMERTA_CONTROL_LOCAL_SECRET_KEY",
            aliases=("AION_CONTROL_LOCAL_SECRET_KEY",),
            default="",
        )
        assert isinstance(raw_key, str)
        try:
            self.key = base64.urlsafe_b64decode(raw_key.encode("ascii"))
        except (ValueError, UnicodeEncodeError):
            self.key = b""
        if len(self.key) not in {16, 24, 32}:
            raise SecretProviderError("OMERTA_CONTROL_LOCAL_SECRET_KEY must be a base64 AES key")

    def _file(self, path: str) -> Path:
        safe = path.strip("/").replace("/", "__")
        return self.root / f"{safe}.json"

    def get_secret(self, path: str) -> dict[str, str]:
        secret_file = self._file(path)
        if not secret_file.exists():
            raise SecretProviderError(f"Secret not found at '{path}'")
        raw = secret_file.read_bytes()
        try:
            if raw.lstrip().startswith(b"{"):
                payload = json.loads(raw.decode("utf-8"))
                self.set_secret(path, payload)
                LOGGER.warning("Migrated a legacy plaintext local proxy secret")
                return payload
            blob = base64.b64decode(raw, validate=True)
            nonce, tag, ciphertext = blob[:12], blob[12:28], blob[28:]
            payload = AES.new(self.key, AES.MODE_GCM, nonce=nonce)
            return json.loads(payload.decrypt_and_verify(ciphertext, tag).decode("utf-8"))
        except (UnicodeDecodeError, ValueError, KeyError, json.JSONDecodeError) as exc:
            raise SecretProviderError("Local proxy secret is encrypted or authenticated incorrectly") from exc

    def set_secret(self, path: str, payload: dict[str, str]) -> None:
        secret_file = self._file(path)
        cipher = AES.new(self.key, AES.MODE_GCM, nonce=secrets.token_bytes(12))
        ciphertext, tag = cipher.encrypt_and_digest(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
        secret_file.write_bytes(base64.b64encode(cipher.nonce + tag + ciphertext))
        try:
            secret_file.chmod(0o600)
        except OSError:
            pass

    def delete_secret(self, path: str) -> None:
        self._file(path).unlink(missing_ok=True)


def _secret_provider():
    disable_secrets = resolve_environment(
        "OMERTA_CONTROL_DISABLE_SECRETS",
        aliases=("AION_CONTROL_DISABLE_SECRETS",),
        default="1",
    )
    if disable_secrets == "1":
        return LocalSecretProvider()
    provider = get_secret_provider()
    if not hasattr(provider, "set_secret"):
        raise SecretProviderError("Configured secret provider cannot write proxy secrets")
    return provider


def _secret_path(profile_id: int) -> str:
    prefix = resolve_environment(
        "OMERTA_PROXY_SECRET_PREFIX",
        aliases=("AION_PROXY_SECRET_PREFIX",),
        default="aion/network/proxy-profiles",
    )
    assert isinstance(prefix, str)
    return f"{prefix.strip('/')}/{profile_id}"


def _materialise_secrets(secrets: ProxySecrets | None) -> dict[str, str]:
    if not secrets:
        return {}
    payload = secrets.model_dump(exclude_none=True)
    return {key: value for key, value in payload.items() if key in SENSITIVE_FIELDS and value}


def _store_secrets(profile: ProxyProfile, secrets: ProxySecrets | None) -> None:
    payload = _materialise_secrets(secrets)
    if not payload:
        return
    path = profile.secret_ref or _secret_path(profile.id)
    _secret_provider().set_secret(path, payload)
    profile.secret_ref = path


def _delete_secrets(profile: ProxyProfile) -> None:
    if profile.secret_ref:
        try:
            _secret_provider().delete_secret(profile.secret_ref)
        except Exception as exc:
            LOGGER.warning(
                "Unable to delete proxy profile secret (error_type=%s)",
                type(exc).__name__,
            )


def _to_out(profile: ProxyProfile) -> ProxyProfileOut:
    return ProxyProfileOut(
        id=profile.id,
        name=profile.name,
        type=profile.type,
        enabled=profile.enabled,
        scope=profile.scope,
        host=profile.host,
        port=profile.port,
        transport=profile.transport,
        security=profile.security,
        sni=profile.sni,
        flow=profile.flow,
        path=profile.path,
        fallback_direct=profile.fallback_direct,
        health_check_url=profile.health_check_url,
        is_default=profile.is_default,
        has_secrets=bool(profile.secret_ref),
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def list_profiles(db: Session, active_only: bool = False) -> list[ProxyProfileOut]:
    query = select(ProxyProfile).order_by(ProxyProfile.scope, ProxyProfile.name)
    if active_only:
        query = query.where(ProxyProfile.enabled.is_(True))
    return [_to_out(row) for row in db.scalars(query).all()]


def resolve_proxy_environment(db: Session, scope: str = "global") -> dict[str, str]:
    profile = db.scalars(
        select(ProxyProfile)
        .where(ProxyProfile.scope.in_([scope, "global"]))
        .where(ProxyProfile.enabled.is_(True))
        .where(ProxyProfile.is_default.is_(True))
        .order_by(desc(ProxyProfile.scope == scope))
    ).first()
    if not profile or profile.type == "direct":
        return {}
    if profile.type == "http":
        proxy = f"http://{profile.host}:{profile.port}"
        return {"HTTP_PROXY": proxy, "HTTPS_PROXY": proxy}
    if profile.type == "socks5":
        return {"ALL_PROXY": f"socks5://{profile.host}:{profile.port}"}
    if profile.type == "vless":
        return {
            "HTTP_PROXY": "http://proxy-router:10809",
            "HTTPS_PROXY": "http://proxy-router:10809",
            "ALL_PROXY": "socks5://proxy-router:10808",
        }
    return {}


def get_profile(db: Session, profile_id: int) -> ProxyProfile | None:
    return db.get(ProxyProfile, profile_id)


def get_profile_out(profile: ProxyProfile) -> ProxyProfileOut:
    return _to_out(profile)


def create_profile(db: Session, payload: ProxyProfileCreate, actor: str, tenant_id: str) -> ProxyProfileOut:
    profile = ProxyProfile(**payload.model_dump(exclude={"secrets"}))
    db.add(profile)
    db.flush()
    _store_secrets(profile, payload.secrets)
    db.commit()
    db.refresh(profile)
    emit_audit("network.proxy_profile.create", actor, tenant_id)
    return _to_out(profile)


def update_profile(
    db: Session,
    profile: ProxyProfile,
    payload: ProxyProfileUpdate,
    actor: str,
    tenant_id: str,
) -> ProxyProfileOut:
    updates = payload.model_dump(exclude_unset=True, exclude={"secrets"})
    for key, value in updates.items():
        setattr(profile, key, value.value if hasattr(value, "value") else value)
    _store_secrets(profile, payload.secrets)
    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    emit_audit("network.proxy_profile.update", actor, tenant_id)
    return _to_out(profile)


def delete_profile(db: Session, profile: ProxyProfile, actor: str, tenant_id: str) -> None:
    _delete_secrets(profile)
    db.delete(profile)
    db.commit()
    emit_audit("network.proxy_profile.delete", actor, tenant_id)


def set_enabled(db: Session, profile: ProxyProfile, enabled: bool, actor: str, tenant_id: str) -> ProxyProfileOut:
    profile.enabled = enabled
    profile.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(profile)
    emit_audit(f"network.proxy_profile.{'enable' if enabled else 'disable'}", actor, tenant_id)
    return _to_out(profile)


def set_default(db: Session, profile: ProxyProfile, actor: str, tenant_id: str) -> ProxyProfileOut:
    for current in db.scalars(select(ProxyProfile).where(ProxyProfile.scope == profile.scope)).all():
        current.is_default = current.id == profile.id
    profile.enabled = True
    db.commit()
    db.refresh(profile)
    emit_audit("network.proxy_profile.set_default", actor, tenant_id)
    return _to_out(profile)


async def run_test(profile: ProxyProfile, actor: str, tenant_id: str, target_url: str | None = None) -> dict[str, object]:
    result = await test_profile(profile, target_url)
    emit_audit("network.proxy_profile.test", actor, tenant_id)
    return result
