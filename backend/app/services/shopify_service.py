"""Real Shopify Admin REST API client. This is a genuine integration, not
a mock — every function here makes (or, when not connected, honestly
declines to make) a real HTTP call to a real Shopify store, using
`app.db.models.ShopifyIntegration`'s stored credentials.

Coexists with, does not replace, `app/tools/mock_tools.py`: the mock
tools still back Servora's own seeded Customer/Order/Ticket data (see
that module's own docstring on why — the tool-only-grounding rule
doesn't care WHICH system a fact came from, only that it came from a
real tool call). A specialist that has both tool sets available decides
per-message which source is relevant; nothing here changes what the
mock tools return or how they're called.

Deliberately uses Shopify's Admin **REST** API (not GraphQL): its `id`
fields are plain integers, which fit the existing `EvidenceRefOut.ref_id:
int` field with zero changes to that shared schema — see
app/agents/specialists.py's `_describe_evidence_refs()` for where a
Shopify lookup's result becomes a `{"type": "shopify_order", ...}`
evidence ref alongside every other evidence type.

Every public function takes `db` first (same calling convention as
mock_tools.py) so a caller never has to separately thread credentials
through — the integration row IS the config.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.db.models import ShopifyIntegration

_log = logging.getLogger(__name__)

# Pinned, like every other versioned external dependency in this repo
# (anthropic==1.5.0, google-genai==2.23.0 in requirements.txt) — an
# unpinned "latest" Admin API version can change response shapes under
# this integration without warning.
API_VERSION = "2024-01"

_MAX_ATTEMPTS = 3
_BASE_BACKOFF_SECONDS = 1.0
# Shopify returns 429 (rate limited) with a real Retry-After header, and
# occasionally a real 5xx — both are worth a real retry; a 4xx that isn't
# 429 (bad request, not found, unauthorized) is never retried, since
# retrying it would just fail identically N times.
_RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


class ShopifyNotConnectedError(Exception):
    """No Shopify store is connected (or it was explicitly disconnected).
    Callers in app/tools/tool_registry.py catch this and turn it into a
    plain, honest tool-result dict — never let it surface to the LLM
    tool-calling loop as a raw exception (same "never a fabricated
    value, never an unhandled crash" pattern the rest of this codebase's
    tools already follow, e.g. mock_tools.check_payment_issue returning
    `{"detected": False, "error": "Order not found"}` rather than
    raising)."""


class ShopifyAPIError(Exception):
    """A real Shopify API call failed after retries were exhausted, or hit
    a non-retryable error (bad credentials, 404, malformed request).
    Carries the real HTTP status code so callers can distinguish "store
    doesn't have this order" (404) from "something is actually broken"
    (5xx) without parsing the message string."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


@dataclass
class ShopifyCredentials:
    store_url: str
    access_token: str


def _get_integration(db: Session) -> ShopifyIntegration:
    """The most-recently-created row is THE connection — see
    ShopifyIntegration's own docstring for why this is convention, not a
    schema constraint."""
    integration = (
        db.query(ShopifyIntegration).order_by(ShopifyIntegration.id.desc()).first()
    )
    if integration is None or integration.status != "connected":
        raise ShopifyNotConnectedError("No Shopify store is connected. Connect one under Settings -> Integrations.")
    return integration


def _normalize_store_url(store_url: str) -> str:
    """Accepts "my-shop", "my-shop.myshopify.com", or a full
    "https://my-shop.myshopify.com" and always returns the bare
    "my-shop.myshopify.com" host — so a user pasting any of the forms
    Shopify itself shows them in different places still connects
    correctly, rather than failing on a URL-formatting technicality."""
    url = store_url.strip().removeprefix("https://").removeprefix("http://").rstrip("/")
    if not url.endswith(".myshopify.com"):
        url = f"{url}.myshopify.com"
    return url


def _base_url(store_url: str) -> str:
    return f"https://{_normalize_store_url(store_url)}/admin/api/{API_VERSION}"


def _headers(access_token: str) -> dict[str, str]:
    return {"X-Shopify-Access-Token": access_token, "Content-Type": "application/json"}


def _request(
    credentials: ShopifyCredentials,
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    client: httpx.Client | None = None,
) -> dict[str, Any]:
    """The one place every Shopify HTTP call goes through — real retries
    (429/5xx, honoring a real `Retry-After` header when Shopify sends
    one, exponential backoff otherwise), real error classification, real
    timeout. `client` is injectable so tests can pass an
    `httpx.MockTransport`-backed client instead of hitting the real
    network — the same "mock the external boundary, not the internal
    wiring" convention this codebase already uses for `call_llm()`."""
    owns_client = client is None
    http_client = client or httpx.Client(base_url=_base_url(credentials.store_url), timeout=10.0)
    try:
        last_error: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                resp = http_client.request(method, path, params=params, headers=_headers(credentials.access_token))
            except httpx.TransportError as exc:
                # A real network-level failure (DNS, connection refused,
                # timeout) — retry the same way as a 5xx, since it's
                # equally transient.
                last_error = exc
                if attempt < _MAX_ATTEMPTS:
                    _log.warning("Shopify request %s %s failed (attempt %s/%s): %s", method, path, attempt, _MAX_ATTEMPTS, exc)
                    time.sleep(_BASE_BACKOFF_SECONDS * attempt)
                    continue
                raise ShopifyAPIError(f"Shopify request failed after {_MAX_ATTEMPTS} attempts: {exc}") from exc

            if resp.status_code < 300:
                return resp.json() if resp.content else {}

            if resp.status_code in _RETRYABLE_STATUS_CODES and attempt < _MAX_ATTEMPTS:
                retry_after = resp.headers.get("Retry-After")
                delay = float(retry_after) if retry_after else _BASE_BACKOFF_SECONDS * attempt
                _log.warning("Shopify request %s %s got %s (attempt %s/%s) — retrying in %.1fs", method, path, resp.status_code, attempt, _MAX_ATTEMPTS, delay)
                time.sleep(delay)
                continue

            # Non-retryable, or retries exhausted — classify honestly
            # rather than a generic "something went wrong".
            if resp.status_code == 401:
                raise ShopifyAPIError("Shopify rejected the access token — it may be invalid or revoked.", status_code=401)
            if resp.status_code == 404:
                raise ShopifyAPIError("Not found on Shopify.", status_code=404)
            raise ShopifyAPIError(f"Shopify returned {resp.status_code}: {resp.text[:200]}", status_code=resp.status_code)

        # Unreachable in practice (the loop always returns or raises),
        # but keeps the type checker honest about last_error's fate.
        raise ShopifyAPIError(f"Shopify request failed after {_MAX_ATTEMPTS} attempts: {last_error}")
    finally:
        if owns_client:
            http_client.close()


def test_connection(store_url: str, access_token: str, *, client: httpx.Client | None = None) -> dict[str, Any]:
    """Verifies credentials actually work BEFORE anything is persisted as
    "connected" — calls Shopify's cheapest real endpoint (the shop's own
    profile). Raises ShopifyAPIError on bad credentials/unreachable
    store; app/api/integrations.py's connect endpoint is the only caller,
    and never saves a row as "connected" if this raises."""
    credentials = ShopifyCredentials(store_url=store_url, access_token=access_token)
    data = _request(credentials, "GET", "/shop.json", client=client)
    return data.get("shop", {})


def _credentials(db: Session) -> ShopifyCredentials:
    integration = _get_integration(db)
    return ShopifyCredentials(store_url=integration.store_url, access_token=integration.access_token)


def get_customer(db: Session, customer_id: int, *, client: httpx.Client | None = None) -> dict | None:
    creds = _credentials(db)
    try:
        data = _request(creds, "GET", f"/customers/{customer_id}.json", client=client)
    except ShopifyAPIError as exc:
        if exc.status_code == 404:
            return None
        raise
    return data.get("customer")


def get_order(db: Session, order_id: int, *, client: httpx.Client | None = None) -> dict | None:
    creds = _credentials(db)
    try:
        data = _request(creds, "GET", f"/orders/{order_id}.json", client=client)
    except ShopifyAPIError as exc:
        if exc.status_code == 404:
            return None
        raise
    return data.get("order")


def get_orders_by_email(db: Session, email: str, *, client: httpx.Client | None = None) -> list[dict]:
    creds = _credentials(db)
    data = _request(creds, "GET", "/orders.json", params={"email": email, "status": "any"}, client=client)
    return data.get("orders", [])


def get_fulfillment_status(db: Session, order_id: int, *, client: httpx.Client | None = None) -> dict | None:
    """Shopify models fulfillment as a sub-resource of an order, not a
    top-level lookup — this composes the order's own
    `fulfillment_status` + its `fulfillments` array into one summary dict
    rather than exposing Shopify's nested shape directly, so the calling
    tool (lookup_shopify_fulfillment) has one flat, predictable result to
    turn into evidence."""
    order = get_order(db, order_id, client=client)
    if order is None:
        return None
    fulfillments = order.get("fulfillments", [])
    return {
        "order_id": order["id"],
        "order_number": order.get("order_number") or order.get("name"),
        "fulfillment_status": order.get("fulfillment_status"),  # None | "partial" | "fulfilled"
        "fulfillments": [
            {
                "id": f.get("id"),
                "status": f.get("status"),
                "tracking_company": f.get("tracking_company"),
                "tracking_number": f.get("tracking_number"),
                "tracking_url": f.get("tracking_url"),
                "created_at": f.get("created_at"),
            }
            for f in fulfillments
        ],
    }


def get_refunds(db: Session, order_id: int, *, client: httpx.Client | None = None) -> list[dict]:
    creds = _credentials(db)
    data = _request(creds, "GET", f"/orders/{order_id}/refunds.json", client=client)
    return data.get("refunds", [])


def search_orders(db: Session, query: str, *, client: httpx.Client | None = None) -> list[dict]:
    """Being honest about a real API limitation: Shopify's REST
    `/orders.json` (unlike its GraphQL Admin API) has no generic
    full-text `query` parameter — only specific filters (`name`, `email`,
    `financial_status`, ...). Rather than invent a param Shopify doesn't
    actually accept, this classifies `query` into the filter it most
    plausibly matches:
      - starts with "#" or is all digits -> Shopify order name/number
        filter (`name`).
      - contains "@" -> `email` filter (delegates to
        get_orders_by_email).
      - anything else -> the closest REST offers is fetching a recent
        page and matching client-side against order name/email, since
        the REST endpoint has nothing better to filter on for free text.
    """
    if "@" in query:
        return get_orders_by_email(db, query, client=client)

    creds = _credentials(db)
    stripped = query.strip()
    if stripped.startswith("#") or stripped.isdigit():
        name = stripped if stripped.startswith("#") else f"#{stripped}"
        data = _request(creds, "GET", "/orders.json", params={"status": "any", "name": name}, client=client)
        return data.get("orders", [])

    data = _request(creds, "GET", "/orders.json", params={"status": "any", "limit": 50}, client=client)
    orders = data.get("orders", [])
    q = query.lower()
    return [
        o for o in orders
        if q in (o.get("name") or "").lower()
        or q in (o.get("email") or "").lower()
        or q in f"{o.get('customer', {}).get('first_name', '')} {o.get('customer', {}).get('last_name', '')}".lower()
    ]
