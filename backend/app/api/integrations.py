"""Settings -> Integrations: connect/disconnect/status for a real Shopify
store. See app/services/shopify_service.py for the actual HTTP client,
and app/db/models.py::ShopifyIntegration for the stored row this reads
and writes.
"""
import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ShopifyConnectRequest, ShopifyStatusOut
from app.db.database import get_db
from app.db.models import InvestigationStep, ShopifyIntegration
from app.services.shopify_service import ShopifyAPIError, test_connection

router = APIRouter(prefix="/api/integrations", tags=["integrations"])


def _latest_integration(db: Session) -> ShopifyIntegration | None:
    return db.query(ShopifyIntegration).order_by(ShopifyIntegration.id.desc()).first()


def _connected_orders_count(db: Session) -> int:
    """Real count, not a placeholder — how many `shopify_order` evidence
    refs have actually been produced by an investigation so far. Reuses
    the existing InvestigationStep.evidence_refs_json rather than a new
    counter column, so this number can never drift from what the
    Investigation Board/Evidence Explorer themselves show (see Phase 4's
    "reuse existing evidence architecture" requirement)."""
    count = 0
    for (evidence_refs_json,) in db.query(InvestigationStep.evidence_refs_json).filter(
        InvestigationStep.evidence_refs_json.isnot(None)
    ):
        if evidence_refs_json and '"shopify_order"' in evidence_refs_json:
            count += sum(1 for ref in json.loads(evidence_refs_json) if ref.get("type") == "shopify_order")
    return count


@router.get("/shopify/status", response_model=ShopifyStatusOut)
def get_shopify_status(db: Session = Depends(get_db)) -> ShopifyStatusOut:
    integration = _latest_integration(db)
    if integration is None:
        return ShopifyStatusOut(connected=False, status="never_connected")
    return ShopifyStatusOut(
        connected=integration.status == "connected",
        store_url=integration.store_url,
        status=integration.status,
        last_sync_at=integration.last_sync_at.isoformat() if integration.last_sync_at else None,
        last_error=integration.last_error,
        connected_orders_count=_connected_orders_count(db) if integration.status == "connected" else None,
    )


@router.post("/shopify/connect", response_model=ShopifyStatusOut)
def connect_shopify(payload: ShopifyConnectRequest, db: Session = Depends(get_db)) -> ShopifyStatusOut:
    """Verifies the credentials against a REAL Shopify API call
    (test_connection) before ever persisting them as "connected" — never
    saves a row that claims to be connected but isn't, which would
    otherwise surface later as a confusing tool failure mid-investigation
    instead of a clear error right here at connect time."""
    try:
        test_connection(payload.store_url, payload.access_token)
    except ShopifyAPIError as exc:
        raise HTTPException(status_code=400, detail=f"Could not connect to Shopify: {exc}") from exc

    integration = _latest_integration(db)
    if integration is None:
        integration = ShopifyIntegration(store_url=payload.store_url, access_token=payload.access_token)
        db.add(integration)
    else:
        integration.store_url = payload.store_url
        integration.access_token = payload.access_token

    integration.status = "connected"
    integration.last_sync_at = datetime.utcnow()
    integration.last_error = None
    db.commit()
    db.refresh(integration)

    return ShopifyStatusOut(
        connected=True,
        store_url=integration.store_url,
        status=integration.status,
        last_sync_at=integration.last_sync_at.isoformat(),
        last_error=None,
        connected_orders_count=_connected_orders_count(db),
    )


@router.post("/shopify/disconnect", response_model=ShopifyStatusOut)
def disconnect_shopify(db: Session = Depends(get_db)) -> ShopifyStatusOut:
    """Marks the row disconnected AND clears the stored credential —
    once a user explicitly disconnects, this app should hold onto zero
    live secrets for that store, not just stop using them. The row
    itself is kept (not deleted) as an audit trail of "a store was once
    connected here", same convention as every other record-not-delete
    table in this codebase (Notification, Ticket, ...)."""
    integration = _latest_integration(db)
    if integration is None or integration.status != "connected":
        raise HTTPException(status_code=400, detail="No Shopify store is currently connected.")

    integration.status = "disconnected"
    integration.access_token = ""
    db.commit()

    return ShopifyStatusOut(connected=False, store_url=integration.store_url, status="disconnected")
