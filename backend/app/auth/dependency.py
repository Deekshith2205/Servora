"""[RBAC] issue #175 (permission middleware) + #176 (route authorization).

The real enforcement point every protected route depends on.
`get_current_actor()` resolves "who is calling" from the demo-
appropriate identity headers the frontend's Role Switcher sets (a
header, not a real session/cookie — see app/db/models.py::User's own
docstring for why: this codebase has no authentication anywhere, and
building one would itself be the architecture redesign the RBAC epic's
own instructions forbid). `require_permission()`/`require_any_permission()`
are the dependency FACTORIES real routes opt into — deliberately
per-route, not global middleware, so each phase's own issues gate
exactly the endpoints their spec names, without touching routes nobody
asked to protect yet.
"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.permissions import has_any_permission, has_permission
from app.auth.roles import ALL_ROLES, CUSTOMER
from app.db.database import get_db
from app.db.models import Customer, User

_FORBIDDEN_DETAIL = "You do not have permission to perform this action."


@dataclass
class CurrentActor:
    """`role=None` is the real, honest "anonymous / unresolved" state —
    never a default role. `customer_id` is only ever set for a Customer
    actor; `user_id` only ever set for a staff actor — the two are
    mutually exclusive, matching how this codebase's identity actually
    works (a Customer row and a User row are different tables, on
    purpose, see User's own docstring)."""

    role: str | None
    customer_id: int | None = None
    user_id: int | None = None
    name: str | None = None


_ANONYMOUS_ACTOR = CurrentActor(role=None)


def get_current_actor(
    db: Session = Depends(get_db),
    x_servora_role: str | None = Header(default=None),
    x_servora_user_id: int | None = Header(default=None),
    x_servora_customer_id: int | None = Header(default=None),
) -> CurrentActor:
    """Missing headers, an unrecognized role string, or a header
    pointing at a real row that turns out not to exist all resolve to
    the SAME anonymous actor — never a silent "assume administrator" or
    a 500. For a staff role, the identity's ACTUAL `role` column (read
    fresh from the `User` row) is what's trusted, not the
    `X-Servora-Role` header's own claim — so a stale or mismatched
    header can never claim a role that user doesn't really have."""
    if x_servora_role not in ALL_ROLES:
        return _ANONYMOUS_ACTOR

    if x_servora_role == CUSTOMER:
        if x_servora_customer_id is None:
            return _ANONYMOUS_ACTOR
        customer = db.get(Customer, x_servora_customer_id)
        if customer is None:
            return _ANONYMOUS_ACTOR
        return CurrentActor(role=CUSTOMER, customer_id=customer.id, name=customer.name)

    if x_servora_user_id is None:
        return _ANONYMOUS_ACTOR
    user = db.get(User, x_servora_user_id)
    if user is None:
        return _ANONYMOUS_ACTOR
    return CurrentActor(role=user.role, user_id=user.id, name=user.name)


def require_permission(permission: str):
    """A dependency FACTORY: `Depends(require_permission("manage_users"))`.
    Raises a real 403 with a plain, generic detail message — never
    leaking which OTHER permissions the caller does or doesn't have (a
    permission-enumeration side channel), per issue #176's own
    acceptance criteria."""

    def _dependency(actor: CurrentActor = Depends(get_current_actor)) -> CurrentActor:
        if not has_permission(actor.role, permission):
            raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
        return actor

    return _dependency


def require_any_permission(*permissions: str):
    """Same as `require_permission()`, but passes if the actor holds
    ANY of the given permissions — the real mechanism issues #194/#196
    both need (a route reachable via more than one role's own grant)."""

    def _dependency(actor: CurrentActor = Depends(get_current_actor)) -> CurrentActor:
        if not has_any_permission(actor.role, *permissions):
            raise HTTPException(status_code=403, detail=_FORBIDDEN_DETAIL)
        return actor

    return _dependency
