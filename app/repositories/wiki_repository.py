import re
import unicodedata

from sqlalchemy.orm import Session

from app.models.wiki import WikiPage


def _slugify(title: str) -> str:
    s = title.lower().strip()
    s = re.sub(r"[–—]", "-", s)
    s = re.sub(r"\s+", "-", s)
    s = re.sub(r"[^a-z0-9а-яё\-]", "", s)
    s = re.sub(r"-+", "-", s)
    s = s.strip("-")
    return s or "page"


class WikiRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all_published(self) -> list[WikiPage]:
        return (
            self.db.query(WikiPage)
            .filter(WikiPage.is_published == True)
            .order_by(WikiPage.position, WikiPage.id)
            .all()
        )

    def get_all(self) -> list[WikiPage]:
        return self.db.query(WikiPage).order_by(WikiPage.position, WikiPage.id).all()

    def get_by_id(self, page_id: int) -> WikiPage | None:
        return self.db.query(WikiPage).filter(WikiPage.id == page_id).first()

    def get_siblings(self, parent_id: int | None, exclude_id: int | None = None) -> list[WikiPage]:
        q = self.db.query(WikiPage).filter(WikiPage.parent_id == parent_id)
        if exclude_id is not None:
            q = q.filter(WikiPage.id != exclude_id)
        return q.order_by(WikiPage.position, WikiPage.id).all()

    def get_max_position(self, parent_id: int | None) -> int:
        q = self.db.query(WikiPage.position).filter(WikiPage.parent_id == parent_id)
        max_pos = q.order_by(WikiPage.position.desc()).first()
        return max_pos[0] if max_pos else 0

    def create(self, payload: dict) -> WikiPage:
        slug = _slugify(payload.get("title", ""))
        base_slug = slug
        counter = 1
        while self.db.query(WikiPage.id).filter(WikiPage.slug == slug).first():
            slug = f"{base_slug}-{counter}"
            counter += 1
        payload["slug"] = slug
        row = WikiPage(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: WikiPage) -> WikiPage:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: WikiPage) -> None:
        self.db.delete(row)
        self.db.commit()
