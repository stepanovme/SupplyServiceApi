from fastapi import HTTPException, status

from app.database import msk_now
from app.models.document_access_setting import (
    BLOCKS_BY_TYPE,
    DocumentAccessSettingCreate,
    DocumentAccessSettingUpdate,
    DocumentAccessSettingsBulkUpdate,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.document_access_setting_repository import DocumentAccessSettingRepository


class DocumentAccessSettingService:
    def __init__(
        self,
        repo: DocumentAccessSettingRepository,
        department_repo: DepartmentRepository | None = None,
    ) -> None:
        self.repo = repo
        self.department_repo = department_repo

    # ── CRUD ──────────────────────────────────────────────────────────────────

    def get_all(self, document_type: str | None = None) -> list[dict]:
        rows = self.repo.get_all(document_type)
        return [self._serialize(r) for r in rows]

    def get_by_id(self, setting_id: str) -> dict:
        row = self.repo.get_by_id(setting_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
        return self._serialize(row)

    def get_settings_by_target(self, user_id: str | None = None, department_id: int | None = None) -> list[dict]:
        rows = self.repo.get_by_target(user_id=user_id, department_id=department_id)
        return [self._serialize(r) for r in rows]

    def create(self, payload: DocumentAccessSettingCreate, user_id: str) -> dict:
        if not payload.user_id and payload.department_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either user_id or department_id is required",
            )
        visible_blocks = self._normalize_blocks(payload.document_type, payload.visible_blocks)
        data = {
            "document_type": payload.document_type,
            "user_id": payload.user_id,
            "department_id": payload.department_id,
            "visibility_mode": payload.visibility_mode,
            "edit_mode": payload.edit_mode,
            "delete_mode": payload.delete_mode,
            "allowed_counterparty_ids": payload.allowed_counterparty_ids,
            "visible_blocks": visible_blocks,
            "created_by": user_id,
        }
        created = self.repo.create(data)
        return self._serialize(created)

    def update(self, setting_id: str, payload: DocumentAccessSettingUpdate, user_id: str) -> dict:
        row = self.repo.get_by_id(setting_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
        data = payload.model_dump(exclude_unset=True)
        if "visible_blocks" in data and data["visible_blocks"] is not None:
            data["visible_blocks"] = self._normalize_blocks(row.document_type, data["visible_blocks"])
        for key, value in data.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, setting_id: str) -> None:
        row = self.repo.get_by_id(setting_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Setting not found")
        self.repo.delete(row)

    def bulk_save(self, target_user_id: str | None, target_department_id: int | None,
                  settings: list[DocumentAccessSettingCreate], actor_user_id: str) -> list[dict]:
        self.repo.delete_by_target(user_id=target_user_id, department_id=target_department_id)
        results = []
        for s in settings:
            s.user_id = s.user_id or target_user_id
            s.department_id = s.department_id if s.department_id is not None else target_department_id
            results.append(self.create(s, actor_user_id))
        return results

    # ── Permission checks (used by contract/act/letter services) ──────────────

    def check_visibility(self, document_type: str, user_id: str, department_ids: list[int]) -> dict:
        """
        Возвращает:
          mode: "all" | "specific" | None
          allowed_counterparty_ids: list[str] | None (None = все)
        """
        settings = self.repo.get_for_user(document_type, user_id, department_ids)
        best_mode = None
        best_cp_ids: list[str] | None = None
        for s in settings:
            if s.visibility_mode == "all":
                return {"mode": "all", "allowed_counterparty_ids": None}
            if s.visibility_mode == "specific":
                best_mode = "specific"
                if s.allowed_counterparty_ids is None:
                    best_cp_ids = None
                elif best_cp_ids is not None:
                    best_cp_ids = list(set(best_cp_ids) | set(s.allowed_counterparty_ids))
                else:
                    best_cp_ids = list(s.allowed_counterparty_ids)
        return {"mode": best_mode, "allowed_counterparty_ids": best_cp_ids}

    def check_edit(self, document_type: str, user_id: str, department_ids: list[int]) -> dict:
        settings = self.repo.get_for_user(document_type, user_id, department_ids)
        for s in settings:
            if s.edit_mode == "all":
                return {"mode": "all", "allowed_counterparty_ids": None}
        specific_ids: list[str] = []
        for s in settings:
            if s.edit_mode == "specific" and s.allowed_counterparty_ids:
                specific_ids.extend(s.allowed_counterparty_ids)
        if specific_ids:
            return {"mode": "specific", "allowed_counterparty_ids": list(set(specific_ids))}
        return {"mode": None, "allowed_counterparty_ids": None}

    def check_delete(self, document_type: str, user_id: str, department_ids: list[int]) -> dict:
        settings = self.repo.get_for_user(document_type, user_id, department_ids)
        for s in settings:
            if s.delete_mode == "all":
                return {"mode": "all", "allowed_counterparty_ids": None}
        specific_ids: list[str] = []
        for s in settings:
            if s.delete_mode == "specific" and s.allowed_counterparty_ids:
                specific_ids.extend(s.allowed_counterparty_ids)
        if specific_ids:
            return {"mode": "specific", "allowed_counterparty_ids": list(set(specific_ids))}
        return {"mode": None, "allowed_counterparty_ids": None}

    def get_visible_blocks(self, document_type: str, user_id: str, department_ids: list[int]) -> dict[str, bool] | None:
        settings = self.repo.get_for_user(document_type, user_id, department_ids)
        if not settings:
            return None
        merged: dict[str, bool] = {}
        for s in settings:
            if s.visible_blocks:
                for block, visible in s.visible_blocks.items():
                    merged[block] = merged.get(block, False) or bool(visible)
        return merged if merged else None

    def is_block_visible(self, document_type: str, user_id: str, department_ids: list[int], block_name: str) -> bool:
        blocks = self.get_visible_blocks(document_type, user_id, department_ids)
        if blocks is None:
            return True
        return blocks.get(block_name, True)

    def check_document_access(
        self,
        document_type: str,
        user_id: str,
        department_ids: list[int],
        counterparty_ids: list[str],
    ) -> dict:
        """
        Проверяет права доступа к конкретному документу.
        Возвращает:
          can_see: bool
          can_edit: bool
          can_delete: bool
          visibility_mode: "all" | "specific" | None
          edit_mode: "all" | "specific" | None
          delete_mode: "all" | "specific" | None
          visible_blocks: dict[str, bool] | None
        """
        settings = self.repo.get_for_user(document_type, user_id, department_ids)

        if not settings:
            return {
                "can_see": False,
                "can_edit": False,
                "can_delete": False,
                "visibility_mode": None,
                "edit_mode": None,
                "delete_mode": None,
                "visible_blocks": None,
            }

        # Visibility
        vis_mode = None
        vis_cp_ids = None
        for s in settings:
            if s.visibility_mode == "all":
                vis_mode = "all"
                vis_cp_ids = None
                break
            if s.visibility_mode == "specific":
                vis_mode = "specific"
                if s.allowed_counterparty_ids is None:
                    vis_cp_ids = None
                elif vis_cp_ids is not None:
                    vis_cp_ids = list(set(vis_cp_ids) | set(s.allowed_counterparty_ids))
                else:
                    vis_cp_ids = list(s.allowed_counterparty_ids)

        can_see = False
        if vis_mode == "all":
            can_see = True
        elif vis_mode == "specific" and vis_cp_ids is not None:
            can_see = any(cp in vis_cp_ids for cp in counterparty_ids)

        # Edit
        edit_mode = None
        edit_cp_ids = None
        for s in settings:
            if s.edit_mode == "all":
                edit_mode = "all"
                edit_cp_ids = None
                break
            if s.edit_mode == "specific":
                edit_mode = "specific"
                if s.allowed_counterparty_ids is None:
                    edit_cp_ids = None
                elif edit_cp_ids is not None:
                    edit_cp_ids = list(set(edit_cp_ids) | set(s.allowed_counterparty_ids))
                else:
                    edit_cp_ids = list(s.allowed_counterparty_ids)

        can_edit = False
        if edit_mode == "all":
            can_edit = True
        elif edit_mode == "specific" and edit_cp_ids is not None:
            can_edit = any(cp in edit_cp_ids for cp in counterparty_ids)

        # Delete
        del_mode = None
        del_cp_ids = None
        for s in settings:
            if s.delete_mode == "all":
                del_mode = "all"
                del_cp_ids = None
                break
            if s.delete_mode == "specific":
                del_mode = "specific"
                if s.allowed_counterparty_ids is None:
                    del_cp_ids = None
                elif del_cp_ids is not None:
                    del_cp_ids = list(set(del_cp_ids) | set(s.allowed_counterparty_ids))
                else:
                    del_cp_ids = list(s.allowed_counterparty_ids)

        can_delete = False
        if del_mode == "all":
            can_delete = True
        elif del_mode == "specific" and del_cp_ids is not None:
            can_delete = any(cp in del_cp_ids for cp in counterparty_ids)

        # Visible blocks
        merged: dict[str, bool] = {}
        for s in settings:
            if s.visible_blocks:
                for block, visible in s.visible_blocks.items():
                    merged[block] = merged.get(block, False) or bool(visible)
        visible_blocks = merged if merged else None

        return {
            "can_see": can_see,
            "can_edit": can_edit,
            "can_delete": can_delete,
            "visibility_mode": vis_mode,
            "edit_mode": edit_mode,
            "delete_mode": del_mode,
            "visible_blocks": visible_blocks,
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    @staticmethod
    def _normalize_blocks(document_type: str, visible_blocks: dict[str, bool] | None) -> dict[str, bool] | None:
        if visible_blocks is None:
            return None
        allowed = BLOCKS_BY_TYPE.get(document_type, [])
        return {k: bool(v) for k, v in visible_blocks.items() if k in allowed}

    def get_additional_visible_ids(
        self,
        document_type: str,
        user_id: str,
        department_ids: list[int],
        get_all_ids_fn,
        get_ids_by_counterparty_fn,
    ) -> list[int]:
        """
        Возвращает дополнительные ID документов, которые пользователь должен видеть
        на основе document_access_settings (помимо тех, где он уже указан).
        """
        settings = self.repo.get_for_user(document_type, user_id, department_ids)
        if not settings:
            return []

        # Определяем лучший режим видимости
        has_all = any(s.visibility_mode == "all" for s in settings)
        if has_all:
            return get_all_ids_fn()

        # Собираем counterparty_ids из "specific" настроек
        specific_cp_ids: list[str] = []
        for s in settings:
            if s.visibility_mode == "specific" and s.allowed_counterparty_ids:
                specific_cp_ids.extend(s.allowed_counterparty_ids)

        if specific_cp_ids:
            return get_ids_by_counterparty_fn(list(set(specific_cp_ids)))

        return []

    @staticmethod
    def _serialize(row) -> dict:
        return {
            "id": row.id,
            "document_type": row.document_type,
            "user_id": row.user_id,
            "department_id": row.department_id,
            "visibility_mode": row.visibility_mode,
            "edit_mode": row.edit_mode,
            "delete_mode": row.delete_mode,
            "allowed_counterparty_ids": row.allowed_counterparty_ids,
            "visible_blocks": row.visible_blocks,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }
