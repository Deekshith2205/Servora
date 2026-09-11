"""STUB. Tracked by issue: "Analytics dashboard (churn/anomaly radar)"."""
from fastapi import APIRouter

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics/summary")
def analytics_summary() -> dict:
    # TODO(issue: analytics-dashboard): real clustering over tickets.
    return {"status": "not_implemented", "recurring_issues": [], "churn_signals": []}
