from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from shared.config.environment import resolve_environment
from shared.telemetry.audit import emit_audit

from .models import ControlConfiguration
from .schemas import ConfigurationProposal

CONFIGURATION_ID = 1


def _default_configuration() -> dict[str, object]:
    router_policy = resolve_environment(
        "OMERTA_ROUTER_POLICY",
        aliases=("AION_ROUTER_POLICY",),
        default="auto",
        blank="preserve",
    )
    local_provider = resolve_environment(
        "OMERTA_LOCAL_PROVIDER",
        aliases=("AION_LOCAL_PROVIDER",),
        blank="preserve",
    )
    api_provider = resolve_environment(
        "OMERTA_API_PROVIDER",
        aliases=("AION_API_PROVIDER",),
        blank="preserve",
    )
    assert isinstance(router_policy, str)
    return {
        "router": {
            "mode": router_policy,
            "local_provider": local_provider or None,
            "api_provider": api_provider or None,
        }
    }


def _decode(value: str | None) -> dict[str, Any] | None:
    if value is None:
        return None
    decoded = json.loads(value)
    return decoded if isinstance(decoded, dict) else None


def _encode(value: dict[str, Any]) -> str:
    return json.dumps(value, separators=(",", ":"), sort_keys=True)


def _state(db: Session) -> ControlConfiguration:
    state = db.get(ControlConfiguration, CONFIGURATION_ID)
    if state is None:
        state = ControlConfiguration(
            id=CONFIGURATION_ID,
            effective_json=_encode(_default_configuration()),
        )
        db.add(state)
        db.commit()
        db.refresh(state)
    return state


def status(db: Session) -> dict[str, object]:
    state = _state(db)
    effective = _decode(state.effective_json) or _default_configuration()
    proposed = _decode(state.proposed_json)
    return {
        "effective": effective,
        "proposed": proposed,
        "has_pending": proposed is not None,
        "can_revert": state.previous_json is not None,
        "updated_at": state.updated_at.isoformat(),
    }


def propose(
    db: Session,
    payload: ConfigurationProposal,
    actor: str,
    tenant_id: str,
) -> dict[str, object]:
    state = _state(db)
    state.proposed_json = _encode(payload.model_dump())
    state.updated_at = datetime.now(UTC)
    db.commit()
    emit_audit("configuration.propose", actor, tenant_id)
    return status(db)


def apply(db: Session, actor: str, tenant_id: str) -> dict[str, object]:
    state = _state(db)
    if state.proposed_json is not None:
        state.previous_json = state.effective_json
        state.effective_json = state.proposed_json
        state.proposed_json = None
        state.updated_at = datetime.now(UTC)
        db.commit()
        emit_audit("configuration.apply", actor, tenant_id)
    return status(db)


def revert(db: Session, actor: str, tenant_id: str) -> dict[str, object]:
    state = _state(db)
    if state.proposed_json is not None:
        state.proposed_json = None
    elif state.previous_json is not None:
        current = state.effective_json
        state.effective_json = state.previous_json
        state.previous_json = current
    state.updated_at = datetime.now(UTC)
    db.commit()
    emit_audit("configuration.revert", actor, tenant_id)
    return status(db)
