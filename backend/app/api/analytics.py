import string
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Customer, Ticket

router = APIRouter(prefix="/api", tags=["analytics"])

STOP_WORDS = {
    "the", "is", "at", "which", "on", "i", "my", "a", "to", "for", "in", "of", "and",
    "that", "this", "it", "with", "as", "are", "be", "was", "have", "has", "not", "but",
    "what", "so", "can", "someone", "got", "but", "an", "from", "they", "we", "me", "you",
    "will", "would", "could", "should", "do", "does", "did", "if", "then", "there", "their",
    "where", "when", "why", "how", "been", "being", "am", "or", "by", "about"
}

THEMES = {
    "SHIPPING_DELAY": {"shipping", "shipment", "shipped", "package", "fulfillment", "delivery", "delayed", "delay", "stuck", "moved"},
    "TRACKING": {"tracking", "track", "trackingnumber", "update", "updated", "movement"}
}

# Issue #16: churn-risk thresholds — a customer with this many still-open
# (unresolved by the AI) tickets in the lookback window is worth flagging to
# staff proactively, before they escalate further or churn.
CHURN_MEDIUM_THRESHOLD = 2
CHURN_HIGH_THRESHOLD = 4

def normalize_text(text: str) -> set[str]:
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    tokens = set(text.split())
    return tokens - STOP_WORDS


def compute_churn_signals(db: Session, cutoff: datetime) -> list[dict]:
    """A customer with several still-unresolved tickets (open OR escalated —
    both mean the AI hasn't closed it out) is a churn risk worth surfacing
    proactively, not just counted per-ticket. Real, queryable data — no
    prediction model, just a threshold on what's actually in the DB.
    """
    unresolved = db.query(Ticket).filter(
        Ticket.status.in_(["open", "escalated"]),
        Ticket.created_at >= cutoff,
    ).all()

    by_customer: dict[int, list[Ticket]] = {}
    for t in unresolved:
        by_customer.setdefault(t.customer_id, []).append(t)

    signals = []
    for customer_id, tix in by_customer.items():
        count = len(tix)
        if count < CHURN_MEDIUM_THRESHOLD:
            continue
        customer = db.get(Customer, customer_id)
        signals.append({
            "customer_id": customer_id,
            "customer_name": customer.name if customer else None,
            "unresolved_ticket_count": count,
            "risk_level": "high" if count >= CHURN_HIGH_THRESHOLD else "medium",
            "categories": sorted({t.category for t in tix if t.category}),
            "ticket_ids": sorted(t.id for t in tix),
        })

    signals.sort(key=lambda s: s["unresolved_ticket_count"], reverse=True)
    return signals


def compute_trend(db: Session, now: datetime, cutoff: datetime, days: int) -> list[dict]:
    """Daily ticket volume over the lookback window, zero-padded so every
    day in the range appears (a real chart needs a continuous x-axis —
    padding with true zeros isn't fabricating data, it's just not omitting
    the days nothing happened)."""
    tickets_in_period = db.query(Ticket).filter(Ticket.created_at >= cutoff).all()
    counts: dict[str, int] = {}
    for t in tickets_in_period:
        day = t.created_at.date().isoformat()
        counts[day] = counts.get(day, 0) + 1

    trend = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        trend.append({"date": day, "count": counts.get(day, 0)})
    return trend


def compute_resolution_and_escalation_rates(db: Session, cutoff: datetime) -> dict:
    processed_tickets = db.query(Ticket).filter(
        Ticket.status.in_(["resolved", "escalated"]),
        Ticket.created_at >= cutoff
    ).all()
    
    total = len(processed_tickets)
    resolved = sum(1 for t in processed_tickets if t.status == "resolved")
    escalated = sum(1 for t in processed_tickets if t.status == "escalated")
    
    if total == 0:
        return {
            "resolution_rate": {"resolved": 0, "total": 0, "rate": 0.0},
            "escalation_rate": {"escalated": 0, "total": 0, "rate": 0.0}
        }
        
    return {
        "resolution_rate": {"resolved": resolved, "total": total, "rate": resolved / total},
        "escalation_rate": {"escalated": escalated, "total": total, "rate": escalated / total}
    }


def compute_sentiment_trend(db: Session, now: datetime, cutoff: datetime, days: int) -> list[dict]:
    tickets_in_period = db.query(Ticket).filter(Ticket.created_at >= cutoff).all()
    
    # Pre-initialize buckets for the last `days` days
    buckets = {}
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        buckets[day] = {"date": day, "positive": 0, "neutral": 0, "negative": 0}
        
    for t in tickets_in_period:
        if not t.sentiment:
            continue
            
        day = t.created_at.date().isoformat()
        if day in buckets and t.sentiment in ["positive", "neutral", "negative"]:
            buckets[day][t.sentiment] += 1
            
    return list(buckets.values())


def compute_confidence_distribution(db: Session, cutoff: datetime) -> dict:
    tickets = db.query(Ticket).filter(
        Ticket.created_at >= cutoff,
        Ticket.confidence.isnot(None)
    ).all()
    
    low = 0
    moderate = 0
    high = 0
    
    for t in tickets:
        c = t.confidence
        if c < 0.60:
            low += 1
        elif c < 0.80:
            moderate += 1
        else:
            high += 1
            
    return {
        "low": low,
        "moderate": moderate,
        "high": high,
        "total": len(tickets)
    }


@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)) -> dict:
    now = datetime.utcnow()
    # 30 calendar days including today (today + 29 previous days)
    # Start from midnight of the 29th day ago.
    cutoff_date = (now - timedelta(days=29)).date()
    cutoff = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)

    open_tickets = db.query(Ticket).filter(
        Ticket.status == "open",
        Ticket.created_at >= cutoff
    ).all()

    # Pre-compute data for each ticket
    ticket_data = []
    for t in open_tickets:
        text = f"{t.subject} {t.message}"
        tokens = normalize_text(text)

        # Determine themes
        matched_themes = set()
        for theme_name, theme_words in THEMES.items():
            if tokens & theme_words:
                matched_themes.add(theme_name)

        ticket_data.append({
            "id": t.id,
            "category": t.category,
            "tokens": tokens,
            "themes": matched_themes
        })

    # Build adjacency list
    n = len(ticket_data)
    adj = {i: [] for i in range(n)}

    for i in range(n):
        for j in range(i + 1, n):
            t1 = ticket_data[i]
            t2 = ticket_data[j]

            # Hybrid deterministic similarity
            is_same_category = (t1["category"] == t2["category"])
            shared_themes = t1["themes"] & t2["themes"]
            shared_tokens = t1["tokens"] & t2["tokens"]

            strong_match = False

            # Rule 1: Same category + shared theme
            if is_same_category and shared_themes:
                strong_match = True
            # Rule 2: Shared multiple meaningful terms (>= 2)
            elif len(shared_tokens) >= 2:
                strong_match = True

            if strong_match:
                adj[i].append(j)
                adj[j].append(i)

    # Connected components
    visited = set()
    clusters = []

    for i in range(n):
        if i not in visited:
            comp = []
            stack = [i]
            while stack:
                node = stack.pop()
                if node not in visited:
                    visited.add(node)
                    comp.append(node)
                    for neighbor in adj[node]:
                        if neighbor not in visited:
                            stack.append(neighbor)
            if len(comp) >= 2:
                clusters.append(comp)

    recurring_issues = []
    for idx, comp in enumerate(clusters):
        t_ids = sorted([ticket_data[i]["id"] for i in comp])

        # Generate deterministic hypothesis
        all_themes = []
        all_tokens = []
        for i in comp:
            all_themes.extend(ticket_data[i]["themes"])
            all_tokens.extend(ticket_data[i]["tokens"])

        theme_counts = {th: all_themes.count(th) for th in set(all_themes)}
        token_counts = {tok: all_tokens.count(tok) for tok in set(all_tokens)}

        if theme_counts:
            dominant_theme = max(theme_counts, key=theme_counts.get)
            if dominant_theme == "SHIPPING_DELAY" or dominant_theme == "TRACKING":
                hypothesis = "Likely root cause: shipment tracking/fulfillment delays affecting multiple orders."
                pattern = "tracking, delayed, stuck, shipment"
            else:
                hypothesis = f"Likely root cause: widespread {dominant_theme.lower()} problem."
                pattern = ", ".join(list(THEMES[dominant_theme])[:3])
        else:
            # Fallback to most common words
            sorted_tokens = sorted(token_counts.items(), key=lambda item: item[1], reverse=True)
            top_words = [w for w, c in sorted_tokens[:3]]
            hypothesis = f"Likely root cause: clustered reports relating to {', '.join(top_words)}."
            pattern = ", ".join(top_words)

        recurring_issues.append({
            "cluster_id": f"cluster-{idx+1}",
            "ticket_count": len(comp),
            "pattern": pattern,
            "root_cause_hypothesis": hypothesis,
            "ticket_ids": t_ids
        })

    churn_signals = compute_churn_signals(db, cutoff)
    trend = compute_trend(db, now, cutoff, days=30)
    rates = compute_resolution_and_escalation_rates(db, cutoff)
    sentiment_trend = compute_sentiment_trend(db, now, cutoff, days=30)
    confidence_distribution = compute_confidence_distribution(db, cutoff)

    return {
        "status": "ok",
        "period": {"days": 30},
        "recurring_issues": recurring_issues,
        "churn_signals": churn_signals,
        "trend": trend,
        "resolution_rate": rates["resolution_rate"],
        "escalation_rate": rates["escalation_rate"],
        "sentiment_trend": sentiment_trend,
        "confidence_distribution": confidence_distribution,
    }
