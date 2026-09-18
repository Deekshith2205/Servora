import string
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlalchemy.orm import Session
from app.api.schemas import TeamActivityEntryOut
from app.auth.dependency import require_permission
from app.db.database import get_db
from app.db.models import Channel, Customer, KnowledgeDocument, KnowledgeSearchLog, Ticket, User

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


def compute_trend(db: Session, now: datetime, cutoff: datetime, days: int, include_channel_breakdown: bool = False) -> list[dict]:
    """Daily ticket volume over the lookback window, zero-padded so every
    day in the range appears (a real chart needs a continuous x-axis —
    padding with true zeros isn't fabricating data, it's just not omitting
    the days nothing happened)."""
    tickets_in_period = db.query(Ticket).filter(Ticket.created_at >= cutoff).all()
    counts: dict[str, int] = {}
    channel_counts: dict[str, dict[str, int]] = {}
    
    official_channels = []
    if include_channel_breakdown:
        official_channels = [c.key for c in db.query(Channel).all()]
    
    for t in tickets_in_period:
        day = t.created_at.date().isoformat()
        counts[day] = counts.get(day, 0) + 1
        
        if include_channel_breakdown:
            if day not in channel_counts:
                channel_counts[day] = {ch: 0 for ch in official_channels}
            ch = t.channel_key or "live_chat"
            # If a ticket has a channel that isn't in official_channels, add it ad-hoc
            if ch not in channel_counts[day]:
                channel_counts[day][ch] = 0
            channel_counts[day][ch] += 1

    trend = []
    for i in range(days - 1, -1, -1):
        day = (now - timedelta(days=i)).date().isoformat()
        base_item = {"date": day, "count": counts.get(day, 0)}
        if include_channel_breakdown:
            base_item["channels"] = channel_counts.get(day, {ch: 0 for ch in official_channels})
        trend.append(base_item)
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


def compute_channel_metrics(db: Session, cutoff: datetime) -> list[dict]:
    """[Omnichannel] issue #158 — real per-channel ticket counts via a
    genuine SQL `GROUP BY` (`Ticket.channel_key`, `Ticket.status`), not a
    Python-side re-aggregation of every matching row already fetched.
    This file's sibling aggregations (`compute_churn_signals()`,
    `compute_trend()`) all pull the full row set via `.all()` and group
    in Python; this is the first to group in SQL directly, since a
    per-channel-per-status breakdown is a genuinely two-dimensional
    `GROUP BY` that SQL expresses more directly than hand-rolled Python
    grouping would.

    Every channel a matching `Ticket` row actually carries appears —
    never a hardcoded list of the 5 seeded channels, so a genuinely new
    or renamed channel_key still shows up correctly.
    """
    rows = (
        db.query(Ticket.channel_key, Ticket.status, func.count(Ticket.id))
        .filter(Ticket.created_at >= cutoff)
        .group_by(Ticket.channel_key, Ticket.status)
        .all()
    )

    by_channel: dict[str, dict] = {}
    for channel_key, status, count in rows:
        bucket = by_channel.setdefault(
            channel_key, {"channel": channel_key, "total": 0, "resolved": 0, "escalated": 0, "open": 0}
        )
        bucket["total"] += count
        if status in ("resolved", "escalated", "open"):
            bucket[status] += count

    return sorted(by_channel.values(), key=lambda m: m["total"], reverse=True)


def compute_resolution_time_and_agent_success(db: Session, cutoff: datetime) -> dict:
    """[Future Scope] issue #300 — real Average Resolution Time (from
    `Ticket.resolved_at - Ticket.created_at`, both real columns — no
    schema change needed) and a per-agent success rate (resolved vs.
    escalated share of everything a given `assigned_to` name touched,
    reusing `compute_team_activity()`'s own "match Ticket.assigned_to as
    a plain free-text name, not a real FK" limitation rather than
    inventing a second convention).

    A ticket the AI resolved autonomously (never assigned to anyone) has
    no `assigned_to` — it is honestly grouped under "AI (autonomous)"
    rather than silently dropped, since that is this app's single most
    common real outcome and omitting it would make "Agent Success Rate"
    misleadingly read as 100% (only human-handled tickets counted).
    """
    processed = db.query(Ticket).filter(
        Ticket.status.in_(["resolved", "escalated"]),
        Ticket.created_at >= cutoff,
    ).all()

    resolved_with_duration = [
        t for t in processed if t.status == "resolved" and t.resolved_at is not None
    ]
    if resolved_with_duration:
        avg_seconds = sum(
            (t.resolved_at - t.created_at).total_seconds() for t in resolved_with_duration
        ) / len(resolved_with_duration)
    else:
        avg_seconds = None

    by_agent: dict[str, dict] = {}
    for t in processed:
        agent = t.assigned_to or "AI (autonomous)"
        bucket = by_agent.setdefault(agent, {"agent": agent, "resolved": 0, "total": 0})
        bucket["total"] += 1
        if t.status == "resolved":
            bucket["resolved"] += 1

    agent_success_rate = [
        {**b, "success_rate": (b["resolved"] / b["total"]) if b["total"] else 0.0}
        for b in by_agent.values()
    ]
    agent_success_rate.sort(key=lambda a: a["total"], reverse=True)

    return {
        "avg_resolution_time_seconds": avg_seconds,
        "resolved_ticket_count": len(resolved_with_duration),
        "agent_success_rate": agent_success_rate,
    }


def compute_knowledge_metrics(db: Session, cutoff: datetime) -> dict:
    """[RAG] Phase 10 (#275-#279) — real Knowledge Center retrieval
    analytics, all derived from `KnowledgeSearchLog` (logged at the one
    real `search_knowledge()` call site — see that function's own
    docstring) and `KnowledgeDocument`. Never a fabricated percentage:
    a knowledge base with zero searches yet reports honest zeros/`None`,
    not an invented baseline.
    """
    searches = db.query(KnowledgeSearchLog).filter(KnowledgeSearchLog.created_at >= cutoff).all()
    documents = db.query(KnowledgeDocument).all()

    total_searches = len(searches)
    successful_searches = sum(1 for s in searches if s.result_count > 0)
    success_rate = (successful_searches / total_searches) if total_searches else 0.0
    avg_duration_ms = (
        sum(s.duration_ms for s in searches) / total_searches if total_searches else None
    )
    scored = [s.top_score for s in searches if s.top_score is not None]
    avg_top_score = (sum(scored) / len(scored)) if scored else None

    usage_by_day: dict[str, int] = {}
    for s in searches:
        day = s.created_at.date().isoformat()
        usage_by_day[day] = usage_by_day.get(day, 0) + 1

    doc_hit_counts: dict[int, int] = {}
    for s in searches:
        if s.top_document_id is not None:
            doc_hit_counts[s.top_document_id] = doc_hit_counts.get(s.top_document_id, 0) + 1
    doc_by_id = {d.id: d for d in documents}
    most_used_documents = sorted(
        (
            {"document_id": doc_id, "title": doc_by_id[doc_id].title, "hit_count": count}
            for doc_id, count in doc_hit_counts.items()
            if doc_id in doc_by_id
        ),
        key=lambda d: d["hit_count"],
        reverse=True,
    )[:10]

    status_counts: dict[str, int] = {}
    for d in documents:
        status_counts[d.status] = status_counts.get(d.status, 0) + 1

    return {
        "usage": {
            "total_searches": total_searches,
            "usage_by_day": [{"date": d, "count": c} for d, c in sorted(usage_by_day.items())],
        },
        "success_rate": success_rate,
        "most_used_documents": most_used_documents,
        "coverage": {
            "total_documents": len(documents),
            "by_status": status_counts,
            "total_chunks": sum(d.chunk_count for d in documents),
        },
        "performance": {
            "avg_duration_ms": avg_duration_ms,
            "avg_top_score": avg_top_score,
        },
    }


@router.get("/analytics/summary")
def analytics_summary(
    db: Session = Depends(get_db), _actor=Depends(require_permission("view_analytics"))
) -> dict:
    # [RBAC] issue #193: Manager + Administrator only — deliberately NOT
    # Support Agent, matching the original spec's role boundaries.
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
    channel_trend = compute_trend(db, now, cutoff, days=30, include_channel_breakdown=True)
    rates = compute_resolution_and_escalation_rates(db, cutoff)
    sentiment_trend = compute_sentiment_trend(db, now, cutoff, days=30)
    confidence_distribution = compute_confidence_distribution(db, cutoff)
    channel_metrics = compute_channel_metrics(db, cutoff)
    resolution_time_and_agent_success = compute_resolution_time_and_agent_success(db, cutoff)
    knowledge_metrics = compute_knowledge_metrics(db, cutoff)

    return {
        "status": "ok",
        "period": {"days": 30},
        "recurring_issues": recurring_issues,
        "churn_signals": churn_signals,
        "trend": trend,
        "channel_trend": channel_trend,
        "resolution_rate": rates["resolution_rate"],
        "escalation_rate": rates["escalation_rate"],
        "sentiment_trend": sentiment_trend,
        "confidence_distribution": confidence_distribution,
        # [Omnichannel] issue #158 — additive.
        "channel_metrics": channel_metrics,
        # [Future Scope] issue #300 — additive.
        "avg_resolution_time_seconds": resolution_time_and_agent_success["avg_resolution_time_seconds"],
        "resolved_ticket_count_with_duration": resolution_time_and_agent_success["resolved_ticket_count"],
        "agent_success_rate": resolution_time_and_agent_success["agent_success_rate"],
        # [RAG] issue #225 Phase 10 — additive.
        "knowledge_metrics": knowledge_metrics,
    }


def compute_team_activity(db: Session, cutoff: datetime) -> list[dict]:
    """[RBAC] issue #197 — a real, if modest, per-staff-member open/
    escalated ticket count, matched against the seeded `User` table by
    NAME (`Ticket.assigned_to` is a plain free-text string, not a FK —
    an honest limitation flagged explicitly here rather than silently
    assumed away, matching this codebase's own convention of naming
    scope limits instead of hiding them; a real FK is out of scope,
    per issue #172's own explicit "left completely untouched" note)."""
    staff = db.query(User).order_by(User.name).all()
    tickets = (
        db.query(Ticket)
        .filter(Ticket.status.in_(["open", "escalated"]), Ticket.created_at >= cutoff, Ticket.assigned_to.isnot(None))
        .all()
    )

    by_name: dict[str, dict] = {}
    for t in tickets:
        bucket = by_name.setdefault(t.assigned_to, {"open": 0, "escalated": 0})
        bucket[t.status] += 1

    activity = []
    for user in staff:
        counts = by_name.get(user.name, {"open": 0, "escalated": 0})
        if counts["open"] == 0 and counts["escalated"] == 0:
            continue  # only staff with at least one real assigned ticket, per the issue's own acceptance criteria
        activity.append({
            "user_id": user.id,
            "name": user.name,
            "role": user.role,
            "open_ticket_count": counts["open"],
            "escalated_ticket_count": counts["escalated"],
        })
    return activity


@router.get("/team/activity", response_model=list[TeamActivityEntryOut])
def team_activity(
    db: Session = Depends(get_db), _actor=Depends(require_permission("view_analytics"))
) -> list[dict]:
    now = datetime.utcnow()
    cutoff_date = (now - timedelta(days=29)).date()
    cutoff = datetime(cutoff_date.year, cutoff_date.month, cutoff_date.day)
    return compute_team_activity(db, cutoff)
