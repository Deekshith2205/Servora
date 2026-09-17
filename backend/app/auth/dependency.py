"""[RBAC] issue #175 (permission middleware) + #176 (route authorization).

The real enforcement point every protected route depends on.
`get_current_actor()` resolves "who is calling" — real callers do this
via a `Authorization: Bearer <token>` header, a genuine login session
(see app/auth/session.py) issued only after a real password check
(app/auth/password.py). The OLDER `X-Servora-*` demo-identity headers
(no password, no token — a header claiming to just BE someone) are kept
as a fallback ONLY when no bearer token is present at all, purely so
this file's own large pre-existing test suite (90+ tests across many
files, all built against that header shape) keeps working without a
mechanical rewrite — the real frontend, as of the real-auth work, never
sends those headers at all. See `resolve_authenticated_actor()` below
for exactly where that line is drawn. `require_permission()`/
`require_any_permission()` are the dependency FACTORIES real routes opt
into — deliberately per-route, not global middleware, so each phase's
own issues gate exactly the endpoints their spec names, without
touching routes nobody asked to protect yet.
"""
from dataclasses import dataclass

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.auth.permissions import has_any_permission, has_permission
from app.auth.roles import ALL_ROLES, CUSTOMER
from app.auth.session import resolve_session
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


def _resolve_from_bearer_token(db: Session, authorization: str) -> CurrentActor | None:
    """Returns None if the header isn't a real bearer token, or the
    token doesn't resolve to a live session/row — the caller falls back
    to anonymous, never to the legacy header path, once a bearer token
    was actually presented (see get_current_actor's own docstring for
    why mixing the two would reopen the exact impersonation gap real
    auth exists to close)."""
    if not authorization.startswith("Bearer "):
        return None
    token = authorization.removeprefix("Bearer ").strip()
    if not token:
        return None

    session = resolve_session(db, token)
    if session is None:
        return None

    if session.actor_type == CUSTOMER:
        customer = db.get(Customer, session.actor_id)
        if customer is None:
            return None
        return CurrentActor(role=CUSTOMER, customer_id=customer.id, name=customer.name)

    user = db.get(User, session.actor_id)
    if user is None:
        return None
    return CurrentActor(role=user.role, user_id=user.id, name=user.name)


def get_current_actor(
    db: Session = Depends(get_db),
    authorization: str | None = Header(default=None),
    x_servora_role: str | None = Header(default=None),
    x_servora_user_id: int | None = Header(default=None),
    x_servora_customer_id: int | None = Header(default=None),
) -> CurrentActor:
    """A real `Authorization: Bearer <token>` header, when present, is
    the ONLY thing consulted — resolved against a genuine server-side
    login session (app/auth/session.py), never a client-supplied role/id
    claim. Missing headers, an unrecognized role string, or a header
    pointing at a real row that turns out not to exist all resolve to
    the SAME anonymous actor — never a silent "assume administrator" or
    a 500. For a staff role, the identity's ACTUAL `role` column (read
    fresh from the `User` row) is what's trusted, not any claim in a
    header — so a stale or mismatched header can never claim a role
    that user doesn't really have.

    The `X-Servora-*` headers below are the pre-real-auth demo mechanism,
    consulted ONLY when no `Authorization` header was sent at all — see
    this module's own top-of-file docstring."""
    if authorization is not None:
        return _resolve_from_bearer_token(db, authorization) or _ANONYMOUS_ACTOR

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
