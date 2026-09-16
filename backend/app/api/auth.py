"""[RBAC] issue #175 — the 2 read endpoints the frontend's Role Switcher
and permission cache depend on. Neither one is itself permission-gated
— `GET /api/auth/permissions` is public reference data (the permission
NAMES, not any user's real data), and `GET /api/auth/me` has to be
reachable by an anonymous actor too, so a fresh session can confirm
"you are not currently acting as anyone" rather than getting a 403
before it even knows who it is.
"""
from fastapi import APIRouter, Depends

from app.api.schemas import CurrentActorOut
from app.auth.dependency import CurrentActor, get_current_actor
from app.auth.permissions import ROLE_PERMISSIONS

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/permissions")
def get_permissions() -> dict[str, list[str]]:
    """The exact map `app/auth/permissions.py::ROLE_PERMISSIONS` holds,
    JSON-serializable (sets become lists) — the frontend's own
    permission cache fetches this once rather than hand-duplicating the
    backend's rule."""
    return {role: sorted(permissions) for role, permissions in ROLE_PERMISSIONS.items()}


@router.get("/me", response_model=CurrentActorOut)
def get_me(actor: CurrentActor = Depends(get_current_actor)) -> CurrentActor:
    return actor
