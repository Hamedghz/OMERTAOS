from __future__ import annotations

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from control.app.service_auth import (
    gateway_service_token_matches,
    require_gateway_service_token,
)
from shared.config.environment import resolve_environment

from .models import get_db, init_db
from .schemas import (
    ProxyProfileCreate,
    ProxyProfileList,
    ProxyProfileOut,
    ProxyProfileUpdate,
    ProxyTestResult,
)
from .service import (
    create_profile,
    delete_profile,
    get_profile,
    get_profile_out,
    list_profiles,
    run_test,
    set_default,
    set_enabled,
    update_profile,
)

router = APIRouter(prefix="/v1/network/proxies", tags=["network-proxies"])


def _roles(x_aion_roles: str | None = Header(default=None)) -> set[str]:
    return {
        role.strip().lower() for role in (x_aion_roles or "").split(",") if role.strip()
    }


def _actor(request: Request) -> str:
    return (
        request.headers.get("x-aion-user-id")
        or request.headers.get("x-request-id")
        or "system"
    )


def _tenant(request: Request) -> str:
    return (
        request.headers.get("tenant-id")
        or request.headers.get("x-tenant-id")
        or "default"
    )


def require_admin(request: Request) -> None:
    require_gateway_service_token(request)


def require_view(request: Request, roles: set[str] = Depends(_roles)) -> bool:
    if gateway_service_token_matches(request):
        return "admin" in roles
    public_status = resolve_environment(
        "OMERTA_NETWORK_PROXY_STATUS_PUBLIC",
        aliases=("AION_NETWORK_PROXY_STATUS_PUBLIC",),
        default="0",
    )
    if public_status == "1":
        return False
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN, detail="Proxy status is not available"
    )


def _must_get(db: Session, profile_id: int):
    profile = get_profile(db, profile_id)
    if not profile:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proxy profile not found"
        )
    return profile


@router.on_event("startup")
def startup() -> None:
    init_db()


@router.get("", response_model=ProxyProfileList)
def list_proxy_profiles(
    db: Session = Depends(get_db), is_admin: bool = Depends(require_view)
) -> ProxyProfileList:
    return ProxyProfileList(items=list_profiles(db, active_only=not is_admin))


@router.post("", response_model=ProxyProfileOut, status_code=status.HTTP_201_CREATED)
def create_proxy_profile(
    payload: ProxyProfileCreate,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProxyProfileOut:
    return create_profile(db, payload, _actor(request), _tenant(request))


@router.get("/{profile_id}", response_model=ProxyProfileOut)
def get_proxy_profile(
    profile_id: int,
    db: Session = Depends(get_db),
    is_admin: bool = Depends(require_view),
) -> ProxyProfileOut:
    profile = _must_get(db, profile_id)
    if not is_admin and not profile.enabled:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Proxy profile not found"
        )
    return get_profile_out(profile)


@router.put("/{profile_id}", response_model=ProxyProfileOut)
def update_proxy_profile(
    profile_id: int,
    payload: ProxyProfileUpdate,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProxyProfileOut:
    return update_profile(
        db, _must_get(db, profile_id), payload, _actor(request), _tenant(request)
    )


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_proxy_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> Response:
    delete_profile(db, _must_get(db, profile_id), _actor(request), _tenant(request))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{profile_id}/enable", response_model=ProxyProfileOut)
def enable_proxy_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProxyProfileOut:
    return set_enabled(
        db, _must_get(db, profile_id), True, _actor(request), _tenant(request)
    )


@router.post("/{profile_id}/disable", response_model=ProxyProfileOut)
def disable_proxy_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProxyProfileOut:
    return set_enabled(
        db, _must_get(db, profile_id), False, _actor(request), _tenant(request)
    )


@router.post("/{profile_id}/test", response_model=ProxyTestResult)
async def test_proxy_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProxyTestResult:
    body = (
        await request.json()
        if request.headers.get("content-length") not in (None, "0")
        else {}
    )
    result = await run_test(
        _must_get(db, profile_id),
        _actor(request),
        _tenant(request),
        body.get("target_url"),
    )
    return ProxyTestResult(**result)


@router.post("/{profile_id}/set-default", response_model=ProxyProfileOut)
def set_default_proxy_profile(
    profile_id: int,
    request: Request,
    db: Session = Depends(get_db),
    _: None = Depends(require_admin),
) -> ProxyProfileOut:
    return set_default(db, _must_get(db, profile_id), _actor(request), _tenant(request))
