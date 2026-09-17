"""[RBAC] issue #175 — the 2 read endpoints the frontend's Role Switcher
and permission cache depend on, plus real login/registration/logout.

Real auth is deliberately narrow in scope: `POST /register` only ever
creates a CUSTOMER — there is no public staff sign-up (anyone could
otherwise register themselves as "administrator"). A staff member's
password is set by an Administrator, via `POST /api/users` (see
app/api/users.py) — the existing admin-only User Management surface,
now also the place a new staff login is provisioned.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token as google_id_token
from sqlalchemy.orm import Session

from app.api.schemas import AuthTokenOut, CurrentActorOut, GoogleSignInRequest, LoginRequest, RegisterRequest
from app.auth.dependency import CurrentActor, get_current_actor
from app.auth.password import hash_password, verify_password
from app.auth.permissions import ROLE_PERMISSIONS
from app.auth.roles import CUSTOMER
from app.auth.session import create_session, invalidate_session
from app.config import settings
from app.db.database import get_db
from app.db.models import Credential, Customer, User

router = APIRouter(prefix="/api/auth", tags=["auth"])

_INVALID_CREDENTIALS = "Invalid email or password."


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


@router.post("/register", response_model=AuthTokenOut)
def register(payload: RegisterRequest, db: Session = Depends(get_db)) -> AuthTokenOut:
    email = payload.email.strip().lower()
    if db.query(Customer).filter(Customer.email == email).first() is not None or db.query(User).filter(
        User.email == email
    ).first() is not None:
        raise HTTPException(status_code=400, detail=f"An account with email '{email}' already exists.")

    customer = Customer(name=payload.name, email=email)
    db.add(customer)
    db.flush()  # need customer.id before the Credential row can reference it

    db.add(Credential(actor_type=CUSTOMER, actor_id=customer.id, password_hash=hash_password(payload.password)))
    db.commit()
    db.refresh(customer)

    session = create_session(db, actor_type=CUSTOMER, actor_id=customer.id)
    return AuthTokenOut(token=session.token, role=CUSTOMER, customer_id=customer.id, name=customer.name)


@router.post("/login", response_model=AuthTokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenOut:
    email = payload.email.strip().lower()

    customer = db.query(Customer).filter(Customer.email == email).first()
    if customer is not None:
        credential = (
            db.query(Credential).filter(Credential.actor_type == CUSTOMER, Credential.actor_id == customer.id).first()
        )
        if credential is not None and verify_password(payload.password, credential.password_hash):
            session = create_session(db, actor_type=CUSTOMER, actor_id=customer.id)
            return AuthTokenOut(token=session.token, role=CUSTOMER, customer_id=customer.id, name=customer.name)
        raise HTTPException(status_code=401, detail=_INVALID_CREDENTIALS)

    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        credential = db.query(Credential).filter(Credential.actor_type == "staff", Credential.actor_id == user.id).first()
        if credential is not None and verify_password(payload.password, credential.password_hash):
            session = create_session(db, actor_type="staff", actor_id=user.id)
            return AuthTokenOut(token=session.token, role=user.role, user_id=user.id, name=user.name)

    # Deliberately the SAME generic 401 whether the email doesn't exist,
    # has no password set yet, or the password was simply wrong — never
    # leaking which one, a real login endpoint's own standard practice.
    raise HTTPException(status_code=401, detail=_INVALID_CREDENTIALS)


@router.post("/google", response_model=AuthTokenOut)
def google_sign_in(payload: GoogleSignInRequest, db: Session = Depends(get_db)) -> AuthTokenOut:
    """Real Google Sign-In — verifies the ID token Google Identity
    Services' JS client (`accounts.google.com/gsi/client`) hands back
    after a real Google login, entirely server-side against Google's own
    public signing keys (`google.oauth2.id_token.verify_oauth2_token`).

    Deliberately the ID-token-verification flow, not the authorization-
    code-exchange one: the code-exchange flow needs the client SECRET on
    this server, a second real credential to protect; the ID-token flow
    needs only the (already-public) Client ID, both here and in the
    frontend's `VITE_GOOGLE_CLIENT_ID` — no secret anywhere in this app
    at all.

    Resolves the SAME way login() does — an existing Customer or staff
    User row matched by email — except no password is ever checked, a
    verified Google identity substitutes for it. A brand-new email
    becomes a new self-service Customer (same policy as `/register`: no
    public staff sign-up), with no Credential row at all — a
    Google-only account, until/unless that person also sets a password
    (not yet a feature)."""
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google Sign-In is not configured.")

    try:
        claims = google_id_token.verify_oauth2_token(
            payload.credential, google_requests.Request(), settings.google_client_id
        )
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid Google credential.")

    if not claims.get("email_verified"):
        raise HTTPException(status_code=401, detail="Google account email is not verified.")
    email = claims["email"].strip().lower()
    google_name = claims.get("name") or email

    customer = db.query(Customer).filter(Customer.email == email).first()
    if customer is not None:
        session = create_session(db, actor_type=CUSTOMER, actor_id=customer.id)
        return AuthTokenOut(token=session.token, role=CUSTOMER, customer_id=customer.id, name=customer.name)

    user = db.query(User).filter(User.email == email).first()
    if user is not None:
        session = create_session(db, actor_type="staff", actor_id=user.id)
        return AuthTokenOut(token=session.token, role=user.role, user_id=user.id, name=user.name)

    customer = Customer(name=google_name, email=email)
    db.add(customer)
    db.commit()
    db.refresh(customer)

    session = create_session(db, actor_type=CUSTOMER, actor_id=customer.id)
    return AuthTokenOut(token=session.token, role=CUSTOMER, customer_id=customer.id, name=customer.name)


@router.post("/logout")
def logout(authorization: str | None = Header(default=None), db: Session = Depends(get_db)) -> dict:
    """Best-effort: a missing/malformed/already-invalid token still
    returns 200 — logging out of a session that's already gone is not
    an error from the caller's point of view, it's just already done."""
    if authorization and authorization.startswith("Bearer "):
        invalidate_session(db, authorization.removeprefix("Bearer ").strip())
    return {"status": "ok"}
