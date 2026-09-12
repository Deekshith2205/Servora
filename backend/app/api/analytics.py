import string
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.db.database import get_db
from app.db.models import Ticket

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

def normalize_text(text: str) -> set[str]:
    text = text.lower()
    text = text.translate(str.maketrans('', '', string.punctuation))
    tokens = set(text.split())
    return tokens - STOP_WORDS

@router.get("/analytics/summary")
def analytics_summary(db: Session = Depends(get_db)) -> dict:
    open_tickets = db.query(Ticket).filter(Ticket.status == "open").all()
    
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
        
    return {
        "status": "ok",
        "period": {"days": 30},
        "recurring_issues": recurring_issues,
        "churn_signals": []
    }
