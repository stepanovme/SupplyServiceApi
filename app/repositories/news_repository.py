import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.news import NewsPost


def _slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[–—]", "-", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9а-яё\-]", "", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s or "post"


class NewsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[NewsPost]:
        return self.db.query(NewsPost).order_by(NewsPost.published_at.desc(), NewsPost.id.desc()).all()

    def get_published(self) -> list[NewsPost]:
        return (
            self.db.query(NewsPost)
            .filter(NewsPost.is_published == True)
            .order_by(NewsPost.published_at.desc(), NewsPost.id.desc())
            .all()
        )

    def get_by_id(self, post_id: int) -> NewsPost | None:
        return self.db.query(NewsPost).filter(NewsPost.id == post_id).first()

    def create(self, payload: dict) -> NewsPost:
        slug = _slugify(payload.get("title", ""))
        base_slug = slug
        counter = 1
        while self.db.query(NewsPost.id).filter(NewsPost.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        payload["slug"] = slug
        row = NewsPost(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: NewsPost) -> NewsPost:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: NewsPost) -> None:
        self.db.delete(row)
        self.db.commit()
