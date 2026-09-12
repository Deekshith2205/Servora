"""Knowledge base articles. Issue #17's approval step: a Learning Agent
draft (see /api/escalations/{id}/resolve) is only ever inserted here once
a staff member explicitly approves it — nothing auto-publishes.
"""
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.schemas import ApproveKBArticleRequest, KBArticleOut
from app.db.database import get_db
from app.db.models import KBArticle

router = APIRouter(prefix="/api", tags=["kb"])


@router.get("/kb-articles", response_model=list[KBArticleOut])
def list_kb_articles(db: Session = Depends(get_db)) -> list[KBArticle]:
    return db.query(KBArticle).all()


@router.post("/kb-articles", response_model=KBArticleOut)
def approve_kb_article(payload: ApproveKBArticleRequest, db: Session = Depends(get_db)) -> KBArticle:
    article = KBArticle(title=payload.title, body=payload.body, tags=",".join(payload.tags))
    db.add(article)
    db.commit()
    db.refresh(article)
    return article
