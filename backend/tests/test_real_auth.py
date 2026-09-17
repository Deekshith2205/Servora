"""Real login/registration/logout — app/api/auth.py's new endpoints,
app/auth/password.py's hashing, and app/auth/session.py's token
lifecycle. See app/auth/dependency.py's own docstring for exactly how a
bearer token and the legacy X-Servora-* demo headers relate to each
other; several tests here lock that boundary in explicitly.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.auth.password import hash_password, verify_password
from app.db.database import SessionLocal
from app.db.models import Credential, Customer, User
from app.main import app
from tests.rbac_headers import customer_headers, staff_headers

client = TestClient(app)


def _google_claims(email, name="Google Test User", email_verified=True):
    return {"email": email, "name": name, "email_verified": email_verified, "sub": "fake-google-sub"}


def _admin_headers():
    with SessionLocal() as db:
        return staff_headers(db, "administrator")


def test_hash_password_roundtrip_and_salting():
    h1 = hash_password("correct horse battery staple")
    h2 = hash_password("correct horse battery staple")
    assert h1 != h2  # a real random salt per call, not a deterministic hash
    assert verify_password("correct horse battery staple", h1)
    assert verify_password("correct horse battery staple", h2)
    assert not verify_password("wrong password", h1)


def test_verify_password_never_raises_on_a_malformed_stored_hash():
    assert verify_password("anything", "not-a-real-hash") is False
    assert verify_password("anything", "") is False


def test_register_creates_a_real_customer_and_credential_row():
    resp = client.post("/api/auth/register", json={
        "name": "Real Auth Test User", "email": "real-auth-signup@example.com", "password": "SignupPass1",
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "customer"
    assert body["customer_id"] is not None
    assert "token" in body and len(body["token"]) > 20
    assert "password" not in body and "password_hash" not in body

    with SessionLocal() as db:
        customer = db.get(Customer, body["customer_id"])
        assert customer is not None
        assert customer.email == "real-auth-signup@example.com"
        credential = db.query(Credential).filter(
            Credential.actor_type == "customer", Credential.actor_id == customer.id
        ).first()
        assert credential is not None
        assert credential.password_hash != "SignupPass1"  # never stored in plaintext


def test_register_rejects_a_duplicate_email():
    payload = {"name": "Dup", "email": "real-auth-dup@example.com", "password": "SignupPass1"}
    first = client.post("/api/auth/register", json=payload)
    assert first.status_code == 200
    second = client.post("/api/auth/register", json=payload)
    assert second.status_code == 400


def test_register_rejects_a_short_password():
    resp = client.post("/api/auth/register", json={
        "name": "Short", "email": "real-auth-short@example.com", "password": "abc",
    })
    assert resp.status_code == 422


def test_login_with_correct_password_succeeds():
    client.post("/api/auth/register", json={
        "name": "Login Test", "email": "real-auth-login@example.com", "password": "LoginPass1",
    })
    resp = client.post("/api/auth/login", json={"email": "real-auth-login@example.com", "password": "LoginPass1"})
    assert resp.status_code == 200
    assert resp.json()["role"] == "customer"


def test_login_with_wrong_password_is_a_generic_401():
    client.post("/api/auth/register", json={
        "name": "Wrong PW", "email": "real-auth-wrongpw@example.com", "password": "CorrectPass1",
    })
    resp = client.post("/api/auth/login", json={"email": "real-auth-wrongpw@example.com", "password": "NopeNotThis1"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_login_with_unknown_email_is_the_same_generic_401():
    """Same message as a wrong password — never leaking whether the
    email itself exists (a real login endpoint's own standard practice)."""
    resp = client.post("/api/auth/login", json={"email": "nobody-real-auth@example.com", "password": "whatever123"})
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid email or password."


def test_admin_created_staff_account_can_log_in():
    create = client.post("/api/users", json={
        "name": "New Staff Login", "email": "real-auth-staff@example.com",
        "role": "support_agent", "password": "StaffPass123",
    }, headers=_admin_headers())
    assert create.status_code == 200

    login = client.post("/api/auth/login", json={"email": "real-auth-staff@example.com", "password": "StaffPass123"})
    assert login.status_code == 200
    body = login.json()
    assert body["role"] == "support_agent"
    assert body["user_id"] == create.json()["id"]


def test_admin_create_user_requires_a_real_password():
    resp = client.post("/api/users", json={
        "name": "No Password", "email": "real-auth-nopw@example.com", "role": "support_agent",
    }, headers=_admin_headers())
    assert resp.status_code == 422


def test_bearer_token_resolves_identity_on_protected_endpoint():
    register = client.post("/api/auth/register", json={
        "name": "Bearer Test", "email": "real-auth-bearer@example.com", "password": "BearerPass1",
    })
    token = register.json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == "customer"
    assert body["customer_id"] == register.json()["customer_id"]


def test_bearer_token_grants_access_to_a_gated_customer_endpoint():
    register = client.post("/api/auth/register", json={
        "name": "Gated Test", "email": "real-auth-gated@example.com", "password": "GatedPass1",
    })
    token = register.json()["token"]

    resp = client.get("/api/tickets/mine", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200


def test_invalid_bearer_token_resolves_to_anonymous_not_a_500():
    me = client.get("/api/auth/me", headers={"Authorization": "Bearer not-a-real-token"})
    assert me.status_code == 200
    assert me.json()["role"] is None

    # And a permission-gated endpoint still correctly 403s for it.
    resp = client.get("/api/users", headers={"Authorization": "Bearer not-a-real-token"})
    assert resp.status_code == 403


def test_logout_invalidates_the_session_token():
    register = client.post("/api/auth/register", json={
        "name": "Logout Test", "email": "real-auth-logout@example.com", "password": "LogoutPass1",
    })
    token = register.json()["token"]
    headers = {"Authorization": f"Bearer {token}"}

    before = client.get("/api/auth/me", headers=headers)
    assert before.json()["role"] == "customer"

    logout = client.post("/api/auth/logout", headers=headers)
    assert logout.status_code == 200

    after = client.get("/api/auth/me", headers=headers)
    assert after.json()["role"] is None


def test_logout_with_no_token_is_still_a_clean_200():
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200


def test_authorization_header_takes_priority_over_legacy_demo_headers():
    """The exact boundary app/auth/dependency.py's docstring describes:
    once a real bearer token is presented, the older X-Servora-* headers
    are ignored entirely for that request — even if they claim to be
    someone else — never merged or fallen back to."""
    register = client.post("/api/auth/register", json={
        "name": "Priority Test", "email": "real-auth-priority@example.com", "password": "PriorityPass1",
    })
    token = register.json()["token"]
    real_customer_id = register.json()["customer_id"]

    with SessionLocal() as db:
        other = customer_headers(1)  # a real, different seeded customer (Alice, id=1)

    resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}", **other})
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == real_customer_id
    assert body["customer_id"] != 1


def test_legacy_demo_headers_still_work_with_no_authorization_header():
    """Unchanged pre-real-auth behavior for the existing 90+ RBAC tests
    that never send Authorization at all — regression guard."""
    with SessionLocal() as db:
        headers = staff_headers(db, "manager")
    resp = client.get("/api/auth/me", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["role"] == "manager"


# -- Real "Sign in with Google" ------------------------------------- #
# google.oauth2.id_token.verify_oauth2_token() is always mocked here —
# it makes a real network call to fetch Google's public signing keys,
# and a genuine signed ID token can only come from a real Google login.
# What's under test is everything AFTER verification: account
# resolution/creation and session issuance.

def test_google_sign_in_not_configured_returns_503():
    with patch("app.api.auth.settings.google_client_id", ""):
        resp = client.post("/api/auth/google", json={"credential": "whatever"})
    assert resp.status_code == 503


def test_google_sign_in_creates_a_new_customer_for_an_unknown_email():
    with patch("app.api.auth.settings.google_client_id", "fake-client-id"), patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims("real-auth-google-new@example.com", name="Gina Google"),
    ):
        resp = client.post("/api/auth/google", json={"credential": "fake-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "customer"
    assert body["name"] == "Gina Google"

    with SessionLocal() as db:
        customer = db.query(Customer).filter(Customer.email == "real-auth-google-new@example.com").first()
        assert customer is not None
        # A Google-only account — no password was ever set, so no Credential row.
        credential = db.query(Credential).filter(Credential.actor_type == "customer", Credential.actor_id == customer.id).first()
        assert credential is None


def test_google_sign_in_resolves_an_existing_customer_by_email_no_duplicate():
    register = client.post("/api/auth/register", json={
        "name": "Existing Before Google", "email": "real-auth-google-existing@example.com", "password": "RealPassword1",
    })
    customer_id = register.json()["customer_id"]

    with patch("app.api.auth.settings.google_client_id", "fake-client-id"), patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims("real-auth-google-existing@example.com", name="Ignored Google Name"),
    ):
        resp = client.post("/api/auth/google", json={"credential": "fake-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["customer_id"] == customer_id
    # The account's own name is kept, not silently overwritten by Google's claim.
    assert body["name"] == "Existing Before Google"

    with SessionLocal() as db:
        assert db.query(Customer).filter(Customer.email == "real-auth-google-existing@example.com").count() == 1


def test_google_sign_in_resolves_an_existing_staff_account_by_email():
    admin_headers = None
    with SessionLocal() as db:
        admin_headers = staff_headers(db, "administrator")
    create = client.post("/api/users", json={
        "name": "Staff Via Google", "email": "real-auth-google-staff@example.com",
        "role": "manager", "password": "StaffRealPass1",
    }, headers=admin_headers)
    user_id = create.json()["id"]

    with patch("app.api.auth.settings.google_client_id", "fake-client-id"), patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims("real-auth-google-staff@example.com"),
    ):
        resp = client.post("/api/auth/google", json={"credential": "fake-token"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["role"] == "manager"
    assert body["user_id"] == user_id


def test_google_sign_in_rejects_an_unverified_email():
    with patch("app.api.auth.settings.google_client_id", "fake-client-id"), patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims("real-auth-google-unverified@example.com", email_verified=False),
    ):
        resp = client.post("/api/auth/google", json={"credential": "fake-token"})
    assert resp.status_code == 401


def test_google_sign_in_rejects_an_invalid_token():
    with patch("app.api.auth.settings.google_client_id", "fake-client-id"), patch(
        "app.api.auth.google_id_token.verify_oauth2_token", side_effect=ValueError("bad token"),
    ):
        resp = client.post("/api/auth/google", json={"credential": "garbage"})
    assert resp.status_code == 401


def test_google_sign_in_issues_a_working_bearer_token():
    with patch("app.api.auth.settings.google_client_id", "fake-client-id"), patch(
        "app.api.auth.google_id_token.verify_oauth2_token",
        return_value=_google_claims("real-auth-google-token-check@example.com"),
    ):
        resp = client.post("/api/auth/google", json={"credential": "fake-token"})
    token = resp.json()["token"]

    me = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200
    assert me.json()["role"] == "customer"
