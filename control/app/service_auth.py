from __future__ import annotations

import secrets

from fastapi import HTTPException, Request, status
from shared.config.environment import resolve_environment


def gateway_service_token_matches(request: Request) -> bool:
    authorization = request.headers.get("authorization") or ""
    if not authorization.startswith("Bearer "):
        return False
    token = authorization.removeprefix("Bearer ")
    configured = resolve_environment(
        "OMERTA_GATEWAY_ADMIN_TOKEN",
        aliases=("AION_GATEWAY_ADMIN_TOKEN", "AION_ADMIN_TOKEN"),
        default="",
    )
    assert isinstance(configured, str)
    return bool(configured and secrets.compare_digest(token, configured))


def require_gateway_service_token(request: Request) -> None:
    if not gateway_service_token_matches(request):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Trusted Gateway authentication required",
        )
