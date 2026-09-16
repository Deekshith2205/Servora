"""Knowledge base articles. Issue #17's approval step: a Learning Agent
draft (see /api/escalations/{id}/resolve) is only ever inserted here once
a staff member explicitly approves it — nothing auto-publishes.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.schemas import ApproveKBArticleRequest, KBArticleOut
from app.auth.dependency import require_permission
from app.db.database import get_db
from app.db.models import KBArticle

router = APIRouter(prefix="/api", tags=["kb"])


@router.get("/kb-articles", response_model=list[KBArticleOut])
def list_kb_articles(db: Session = Depends(get_db)) -> list[KBArticle]:
    return db.query(KBArticle).all()


@router.get("/kb-articles/{article_id}", response_model=KBArticleOut)
def get_kb_article(article_id: int, db: Session = Depends(get_db)) -> KBArticle:
    """[EXPLAIN] issue #95: single-article lookup — backs the Evidence
    Explorer's "Policy References" inline preview (a policy_references
    entry is a `kb_article` evidence ref carrying this same id)."""
    article = db.get(KBArticle, article_id)
    if article is None:
        raise HTTPException(status_code=404, detail=f"KB article {article_id} not found")
    return article


@router.post("/kb-articles", response_model=KBArticleOut)
def approve_kb_article(
    payload: ApproveKBArticleRequest,
    db: Session = Depends(get_db),
    _actor=Depends(require_permission("manage_knowledge_base")),
) -> KBArticle:
    # [RBAC] issue #203: approving a Learning-Agent-drafted article is a
    # content-publishing action, Administrator only — GET /kb-articles
    # (read) stays open above, unaffected, so the Evidence Explorer's KB
    # citations keep working for every staff role.
    article = KBArticle(title=payload.title, body=payload.body, tags=",".join(payload.tags))
    db.add(article)
    db.commit()
    db.refresh(article)
    return article
