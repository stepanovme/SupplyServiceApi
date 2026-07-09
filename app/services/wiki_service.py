import uuid
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.database import msk_now
from app.models.wiki import WikiPage, WikiPageCreate, WikiPageUpdate
from app.models.wiki_file import WikiFileResponse
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.wiki_file_repository import WikiFileRepository
from app.repositories.wiki_repository import WikiRepository

WIKI_FILES_DIR = "/home/webserver/models/supply/wiki"


class WikiService:
    def __init__(
        self,
        repo: WikiRepository,
        auth_user_repo: AuthUserRepository | None = None,
        file_repo: WikiFileRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.file_repo = file_repo

    def get_tree(self) -> list[dict]:
        rows = self.repo.get_all()
        by_id = {r.id: self._serialize_tree_node(r) for r in rows}
        roots = []
        for r in rows:
            node = by_id[r.id]
            node["children"] = []
            if r.parent_id and r.parent_id in by_id:
                by_id[r.parent_id]["children"].append(node)
            else:
                roots.append(node)
        self._sort_children(roots)
        return roots

    def _sort_children(self, nodes: list[dict]) -> None:
        nodes.sort(key=lambda n: (n.get("position") or 0, n.get("id") or 0))
        for n in nodes:
            self._sort_children(n.get("children", []))

    def get_by_id(self, page_id: int) -> dict:
        row = self.repo.get_by_id(page_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
        return self._serialize(row)

    def create(self, payload: WikiPageCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        max_pos = self.repo.get_max_position(data.get("parent_id"))
        data["position"] = max_pos + 1
        if "content" not in data or data.get("content") is None:
            data["content"] = {}
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, page_id: int, payload: WikiPageUpdate, user_id: str) -> dict:
        row = self.repo.get_by_id(page_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize(row)

        old_parent_id = row.parent_id
        old_position = row.position
        parent_changed = "parent_id" in updates and updates["parent_id"] != old_parent_id
        position_changed = "position" in updates and updates["position"] != old_position

        if parent_changed:
            new_parent = updates["parent_id"]
            if "position" in updates and updates["position"] is not None:
                new_position = updates["position"]
            else:
                new_position = self.repo.get_max_position(new_parent) + 1
        elif position_changed:
            new_position = updates["position"]
        else:
            new_position = old_position

        # Apply updates before reindexing
        for key, value in updates.items():
            setattr(row, key, value)
        row.position = new_position
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.repo.save(row)

        # Reindex old parent siblings
        if parent_changed:
            old_siblings = self.repo.get_siblings(old_parent_id, exclude_id=page_id)
            for i, sib in enumerate(old_siblings):
                sib.position = i
            # Reindex new parent siblings
            new_siblings = self.repo.get_siblings(new_parent, exclude_id=page_id)
            for i, sib in enumerate(new_siblings):
                pos = i
                if pos >= new_position:
                    pos += 1
                sib.position = pos
            self.repo.db.commit()
        elif position_changed:
            siblings = self.repo.get_siblings(row.parent_id, exclude_id=page_id)
            for i, sib in enumerate(siblings):
                pos = i
                if pos >= new_position:
                    pos += 1
                sib.position = pos
            self.repo.db.commit()

        self.repo.db.refresh(row)
        return self._serialize(row)

    def upload_file(self, file: "UploadFile", user_id: str) -> dict:
        Path(WIKI_FILES_DIR).mkdir(parents=True, exist_ok=True)
        ext = Path(file.filename or "file").suffix
        storage_name = f"{uuid.uuid4()}{ext}"
        file_path = f"{WIKI_FILES_DIR}/{storage_name}"

        content = file.file.read()
        with open(file_path, "wb") as f:
            f.write(content)

        if self.file_repo is None:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="File repo not available")

        record = self.file_repo.create({
            "filename": file.filename or storage_name,
            "path": file_path,
            "url": f"/apisup/supply/media/wiki/{storage_name}",
            "mime": file.content_type or "application/octet-stream",
            "size": len(content),
            "created_by": user_id,
        })
        return {"id": record.id, "url": record.url}

    def get_file_path(self, filename: str) -> str:
        return f"{WIKI_FILES_DIR}/{filename}"

    def delete(self, page_id: int) -> None:
        row = self.repo.get_by_id(page_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Page not found")
        self.repo.delete(row)

    # --- Serialization ---

    def _map_user(self, user) -> dict | None:
        if not user:
            return None
        surname = getattr(user, "surname", "") or ""
        name = getattr(user, "name", "") or ""
        patronymic = getattr(user, "patronymic", "") or ""
        short_fio = f"{surname} {name[0]}.{patronymic[0]}." if surname and name else (surname or name or "")
        return {"id": user.id, "surname": surname, "name": name, "patronymic": patronymic, "short_fio": short_fio}

    def _get_users_map(self, user_ids: list[str]) -> dict:
        if not self.auth_user_repo or not user_ids:
            return {}
        users = self.auth_user_repo.get_by_ids(user_ids)
        return {u.id: u for u in users}

    def _serialize(self, row: WikiPage) -> dict:
        users_by_id = self._get_users_map([row.created_by, row.updated_by] if row.updated_by else [row.created_by])
        return {
            "id": row.id,
            "title": row.title,
            "slug": row.slug,
            "parent_id": row.parent_id,
            "kind": row.kind,
            "content": row.content,
            "position": row.position,
            "is_published": row.is_published,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "updated_by_user": self._map_user(users_by_id.get(row.updated_by)) if row.updated_by else None,
        }

    @staticmethod
    def _serialize_tree_node(row: WikiPage) -> dict:
        return {
            "id": row.id,
            "title": row.title,
            "slug": row.slug,
            "kind": row.kind,
            "parent_id": row.parent_id,
            "position": row.position,
        }
