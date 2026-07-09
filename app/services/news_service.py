import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.database import msk_now
from app.models.news import NewsPost, NewsPostCreate, NewsPostUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.news_repository import NewsRepository

NEWS_FILES_DIR = "/home/webserver/models/supply/news"


class NewsService:
    def __init__(self, repo: NewsRepository, auth_user_repo: AuthUserRepository | None = None) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

    def get_all(self) -> list[dict]:
        rows = self.repo.get_all()
        return [self._serialize_short(r) for r in rows]

    def get_published(self) -> list[dict]:
        rows = self.repo.get_published()
        return [self._serialize_short(r) for r in rows]

    def get_by_id(self, post_id: int) -> dict:
        row = self.repo.get_by_id(post_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        return self._serialize_detail(row)

    def create(self, payload: NewsPostCreate, created_by: str) -> dict:
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = created_by
        if "published_at" not in data or data["published_at"] is None:
            data["published_at"] = msk_now()
        row = self.repo.create(data)
        return self._serialize_short(row)

    def update(self, post_id: int, payload: NewsPostUpdate, user_id: str) -> dict:
        row = self.repo.get_by_id(post_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_detail(row)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save(row)
        return self._serialize_detail(updated)

    def delete(self, post_id: int) -> None:
        row = self.repo.get_by_id(post_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")
        self.repo.delete(row)

    def upload_file(self, file: UploadFile, user_id: str) -> dict:
        Path(NEWS_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{NEWS_FILES_DIR}/{storage_name}"

        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        return {"url": f"/apisup/supply/media/news/{storage_name}"}

    # --- Serialization ---

    def _serialize_short(self, row: NewsPost) -> dict:
        return {
            "id": row.id,
            "title": row.title,
            "cover": row.cover,
            "excerpt": row.excerpt,
            "published_at": row.published_at,
            "created_at": row.created_at,
            "is_published": row.is_published,
        }

    def _serialize_detail(self, row: NewsPost) -> dict:
        return {
            "id": row.id,
            "title": row.title,
            "slug": row.slug,
            "cover": row.cover,
            "excerpt": row.excerpt,
            "content": row.content,
            "is_published": row.is_published,
            "published_at": row.published_at,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }
