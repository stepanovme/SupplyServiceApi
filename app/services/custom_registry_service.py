import math
import os
import re
import subprocess
import uuid
from datetime import date
from pathlib import Path

from fastapi import HTTPException, UploadFile, status

from app.database import msk_now
from app.models.custom_registry import (
    BlockCreate, BlockUpdate, CustomRegistry, CustomRegistryBlock, CustomRegistryField, CustomRegistryRecord,
    ACCESS_FLAGS, AccessCreate, AccessUpdate, CustomRegistryAccess, CustomRegistryFile, CustomRegistryValue, FieldCreate, FieldUpdate, LayoutUpdate, RecordValues, RegistryCreate, RegistryUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.custom_registry_repository import CustomRegistryRepository
from app.repositories.documents_link_repository import DocumentsLinkRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository

CUSTOM_REGISTRY_FILES_DIR = os.getenv("SUPPLY_CUSTOM_REGISTRY_FILES_DIR", "/home/webserver/models/supply/custom_registries")
PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}
ADMIN_ROLE_ID = "697afdbf-4f2e-47fb-8277-7127b9b85317"
TYPE_LABELS = {
    "text": "Текст", "textarea": "Многострочный текст", "number": "Число", "money": "Сумма", "date": "Дата",
    "boolean": "Да / нет", "select": "Выбор из списка", "multiselect": "Выбор нескольких из списка",
    "counterparty": "Компания (контрагент)", "user": "Пользователь", "object": "Объект",
}
TRANSLIT = dict(zip("абвгдеёжзийклмнопрстуфхцчшщъыьэюя", ["a", "b", "v", "g", "d", "e", "e", "zh", "z", "i", "y", "k", "l", "m", "n", "o", "p", "r", "s", "t", "u", "f", "h", "c", "ch", "sh", "sch", "", "y", "", "e", "yu", "ya"]))
NO_RIGHTS = {
    "can_create_registries": "Нет прав создавать реестры",
    "can_view": "Нет доступа к этому реестру",
    "can_add_records": "Нет прав добавлять записи в этот реестр",
    "can_edit_records": "Нет прав редактировать записи этого реестра",
    "can_delete_records": "Нет прав удалять записи этого реестра",
    "can_manage_files": "Нет прав загружать и удалять файлы в этом реестре",
    "can_edit_structure": "Нет прав менять структуру этого реестра (название, блоки, поля)",
    "can_delete_registry": "Нет прав удалять этот реестр",
}
MAX_TEXT = 1000
MAX_TEXTAREA = 20000


def _fail(message: str, status_code: int = status.HTTP_422_UNPROCESSABLE_ENTITY, **extra):
    raise HTTPException(status_code=status_code, detail={"message": message, **extra} if extra else message)


def _empty(value) -> bool:
    return value is None or value == "" or value == [] or value == {}


class CustomRegistryService:
    def __init__(
        self,
        repo: CustomRegistryRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
        department_repo=None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.department_repo = department_repo
        self._perm_cache: dict[str, dict] = {}

    # ---- permissions -----------------------------------------------------------------
    def _is_admin(self, user_id: str) -> bool:
        return bool(self.auth_user_repo and self.auth_user_repo.has_role(user_id, ADMIN_ROLE_ID))

    def _require_admin(self, user_id: str) -> None:
        if not self._is_admin(user_id):
            _fail("Права на реестры настраивает только администратор", status.HTTP_403_FORBIDDEN)

    def _perms(self, user_id: str) -> dict:
        """{"admin": bool, "all": {flag: bool}, "registries": {registry_id: {flag: bool}}} - rules of the user and of the user's departments are summed up."""
        if user_id in self._perm_cache:
            return self._perm_cache[user_id]
        flags = [f for f in ACCESS_FLAGS]
        perms = {"admin": self._is_admin(user_id), "all": {f: False for f in flags}, "registries": {}}
        dept_ids = self.department_repo.get_department_ids_for_user(user_id) if self.department_repo else []
        for rule in self.repo.get_access_rules_for(user_id, dept_ids):
            if rule.all_registries:
                for f in flags:
                    perms["all"][f] = perms["all"][f] or bool(getattr(rule, f))
            else:
                for rid in rule.registry_ids or []:
                    cur = perms["registries"].setdefault(int(rid), {f: False for f in flags})
                    for f in flags:
                        cur[f] = cur[f] or bool(getattr(rule, f))
        self._perm_cache[user_id] = perms
        return perms

    def _can(self, user_id: str, registry_id: int | None, flag: str) -> bool:
        perms = self._perms(user_id)
        if perms["admin"] or perms["all"].get(flag):
            return True
        return registry_id is not None and bool(perms["registries"].get(registry_id, {}).get(flag))

    def _require(self, user_id: str, registry_id: int, flag: str) -> None:
        self._registry(registry_id)  # 404 first, so a missing registry is not reported as a lack of rights
        if not self._can(user_id, registry_id, flag):
            _fail(NO_RIGHTS[flag], status.HTTP_403_FORBIDDEN)

    def _registry_permissions(self, user_id: str, registry_id: int) -> dict:
        return {f: self._can(user_id, registry_id, f) for f in ACCESS_FLAGS if f != "can_create_registries"}

    def my_access(self, user_id: str) -> dict:
        perms = self._perms(user_id)
        registries = {}
        for r in self.repo.list_registries():
            registries[r.id] = self._registry_permissions(user_id, r.id)
        return {"is_admin": perms["admin"], "can_create_registries": self._can(user_id, None, "can_create_registries"),
                "registries": {rid: p for rid, p in registries.items() if p["can_view"]}}

    # ---- access rules (administrator) -------------------------------------------------
    def list_access(self, user_id: str, subject_user_id: str | None, department_id: int | None) -> list[dict]:
        self._require_admin(user_id)
        rules = self.repo.get_access_rules(subject_user_id, department_id)
        names = {r.id: r.name for r in self.repo.list_registries()}
        users = self._users([r.user_id for r in rules if r.user_id])
        return [self._rule(r, names, users) for r in rules]

    def create_access(self, payload: AccessCreate, user_id: str) -> dict:
        self._require_admin(user_id)
        if bool(payload.user_id) == bool(payload.department_id):
            _fail("Укажите ровно одно: user_id или department_id")
        if payload.user_id and not self._users([payload.user_id]):
            _fail("Пользователь не найден", status.HTTP_404_NOT_FOUND)
        ids = self._rule_registry_ids(payload.all_registries, payload.registry_ids)
        row = self.repo.add(CustomRegistryAccess(
            id=str(uuid.uuid4()), user_id=payload.user_id, department_id=payload.department_id,
            all_registries=payload.all_registries, registry_ids=ids, created_by=user_id,
            **{f: bool(getattr(payload, f)) for f in ACCESS_FLAGS},
        ))
        self.repo.commit()
        return self._rule(row, {r.id: r.name for r in self.repo.list_registries()}, self._users([row.user_id] if row.user_id else []))

    def update_access(self, rule_id: str, payload: AccessUpdate, user_id: str) -> dict:
        self._require_admin(user_id)
        row = self._rule_row(rule_id)
        updates = payload.model_dump(exclude_unset=True)
        all_regs = updates.get("all_registries", row.all_registries)
        if "all_registries" in updates or "registry_ids" in updates:
            row.registry_ids = self._rule_registry_ids(all_regs, updates.get("registry_ids", row.registry_ids or []))
            row.all_registries = bool(all_regs)
        for f in ACCESS_FLAGS:
            if updates.get(f) is not None:
                setattr(row, f, updates[f])
        self.repo.touch(row, user_id)
        self.repo.commit()
        return self._rule(row, {r.id: r.name for r in self.repo.list_registries()}, self._users([row.user_id] if row.user_id else []))

    def delete_access(self, rule_id: str, user_id: str) -> None:
        self._require_admin(user_id)
        self.repo.delete(self._rule_row(rule_id))
        self.repo.commit()

    def _rule_registry_ids(self, all_registries: bool, registry_ids: list[int]) -> list[int] | None:
        if all_registries:
            return None
        ids = list(dict.fromkeys(registry_ids or []))
        existing = {r.id for r in self.repo.list_registries()}
        missing = [i for i in ids if i not in existing]
        if missing:
            _fail(f"Реестры не найдены: {', '.join(map(str, missing))}", status.HTTP_404_NOT_FOUND)
        if not ids:
            _fail("Выберите реестры (registry_ids) или поставьте all_registries=true")
        return ids

    def _rule_row(self, rule_id: str) -> CustomRegistryAccess:
        row = self.repo.get_access_rule(rule_id)
        if not row:
            _fail("Правило не найдено", status.HTTP_404_NOT_FOUND)
        return row

    def _rule(self, r: CustomRegistryAccess, names: dict, users: dict) -> dict:
        return {"id": r.id, "user_id": r.user_id, "user": users.get(r.user_id), "department_id": r.department_id,
                "all_registries": bool(r.all_registries), "registry_ids": r.registry_ids or [],
                "registries": [{"id": i, "name": names.get(i)} for i in (r.registry_ids or [])],
                **{f: bool(getattr(r, f)) for f in ACCESS_FLAGS},
                "created_at": r.created_at, "created_by": r.created_by, "updated_at": r.updated_at, "updated_by": r.updated_by}

    # ---- registries -----------------------------------------------------------------
    def meta(self) -> dict:
        return {"field_types": [{"type": k, "label": v, "supports_multiple": k in ("counterparty", "user", "object"),
                                 "needs_options": k in ("select", "multiselect")} for k, v in TYPE_LABELS.items()]}

    def list_registries(self, user_id: str) -> list[dict]:
        counts = self.repo.records_counts()
        return [{"id": r.id, "name": r.name, "description": r.description, "records_count": counts.get(r.id, 0),
                 "permissions": self._registry_permissions(user_id, r.id),
                 "created_at": r.created_at, "created_by": r.created_by}
                for r in self.repo.list_registries() if self._can(user_id, r.id, "can_view")]

    def create_registry(self, payload: RegistryCreate, user_id: str) -> dict:
        if not self._can(user_id, None, "can_create_registries"):
            _fail(NO_RIGHTS["can_create_registries"], status.HTTP_403_FORBIDDEN)
        name = payload.name.strip()
        if self.repo.get_registry_by_name(name):
            _fail("Реестр с таким названием уже есть", status.HTTP_409_CONFLICT)
        row = self.repo.add(CustomRegistry(name=name, description=payload.description, created_by=user_id))
        self._log(row.id, None, user_id, "registry_created", f"Создан реестр «{name}»")
        if not self._perms(user_id)["admin"]:  # the author gets full rights on the registry they created
            self.repo.add(CustomRegistryAccess(
                id=str(uuid.uuid4()), user_id=user_id, all_registries=False, registry_ids=[row.id], created_by=user_id,
                **{f: f != "can_create_registries" for f in ACCESS_FLAGS},
            ))
            self._perm_cache.pop(user_id, None)
        self.repo.commit()
        return self._registry_view(row.id, user_id)

    def update_registry(self, registry_id: int, payload: RegistryUpdate, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_edit_structure")
        row = self._registry(registry_id)
        updates = payload.model_dump(exclude_unset=True)
        if updates.get("name"):
            other = self.repo.get_registry_by_name(updates["name"].strip())
            if other and other.id != row.id:
                _fail("Реестр с таким названием уже есть", status.HTTP_409_CONFLICT)
            row.name = updates["name"].strip()
        if "description" in updates:
            row.description = updates["description"]
        self._log(row.id, None, user_id, "registry_updated", f"Изменён реестр «{row.name}»")
        self.repo.touch(row, user_id)
        self.repo.commit()
        return self._registry_view(registry_id, user_id)

    def delete_registry(self, registry_id: int, user_id: str, force: bool) -> None:
        self._require(user_id, registry_id, "can_delete_registry")
        row = self._registry(registry_id)
        count = self.repo.count_records(registry_id)
        if count and not force:
            _fail(f"В реестре {count} записей. Они будут удалены вместе с ним: повторите запрос с force=true", status.HTTP_409_CONFLICT)
        paths = self.repo.file_paths_for_registry(registry_id)
        links = DocumentsLinkRepository(self.repo.db)
        for rid in self.repo.record_ids(registry_id):
            links.delete_for_document("registry_record", str(rid))
        self.repo.delete(row)
        for rule in self.repo.all_access_rules():  # the deleted registry disappears from the rules too
            if rule.registry_ids and registry_id in rule.registry_ids:
                rule.registry_ids = [i for i in rule.registry_ids if i != registry_id]
        self.repo.commit()
        for path in paths:
            self._remove_from_disk(path)

    def get_registry(self, registry_id: int, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_view")
        return self._registry_view(registry_id, user_id)

    def _registry_view(self, registry_id: int, user_id: str) -> dict:
        row = self._registry(registry_id)
        blocks, fields = self.repo.get_blocks(registry_id), self.repo.get_fields(registry_id)
        by_block: dict[int | None, list] = {}
        for f in fields:
            by_block.setdefault(f.block_id, []).append(self._field(f))
        out_blocks = [{"id": b.id, "name": b.name, "sort_order": b.sort_order, "fields": by_block.get(b.id, [])} for b in blocks]
        if by_block.get(None):
            out_blocks.append({"id": None, "name": "Без блока", "sort_order": None, "fields": by_block[None]})
        return {"id": row.id, "name": row.name, "description": row.description, "records_count": self.repo.count_records(registry_id),
                "permissions": self._registry_permissions(user_id, registry_id),
                "list_columns": [f["key"] for f in map(self._field, fields) if f["show_in_list"]],
                "blocks": out_blocks, "created_at": row.created_at, "created_by": row.created_by,
                "updated_at": row.updated_at, "updated_by": row.updated_by}

    # ---- blocks ---------------------------------------------------------------------
    def create_block(self, registry_id: int, payload: BlockCreate, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_edit_structure")
        order = max([b.sort_order for b in self.repo.get_blocks(registry_id)], default=-1) + 1
        self.repo.add(CustomRegistryBlock(registry_id=registry_id, name=payload.name.strip(), sort_order=order))
        self._log(registry_id, None, user_id, "block_created", f"Добавлен блок «{payload.name.strip()}»")
        self.repo.commit()
        return self._registry_view(registry_id, user_id)

    def update_block(self, block_id: int, payload: BlockUpdate, user_id: str) -> dict:
        block = self._block(block_id)
        self._require(user_id, block.registry_id, "can_edit_structure")
        old = block.name
        if payload.name:
            block.name = payload.name.strip()
            self._log(block.registry_id, None, user_id, "block_updated", f"Блок «{old}» переименован в «{block.name}»")
        self.repo.commit()
        return self._registry_view(block.registry_id, user_id)

    def delete_block(self, block_id: int, user_id: str) -> dict:
        block = self._block(block_id)
        self._require(user_id, block.registry_id, "can_edit_structure")
        registry_id = block.registry_id
        self._log(registry_id, None, user_id, "block_deleted", f"Удалён блок «{block.name}»")
        self.repo.delete(block)  # поля блока остаются в реестре без блока (FK SET NULL)
        self.repo.commit()
        self.repo.db.expire_all()
        return self._registry_view(registry_id, user_id)

    # ---- fields ---------------------------------------------------------------------
    def create_field(self, registry_id: int, payload: FieldCreate, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_edit_structure")
        existing = self.repo.get_fields(registry_id)
        self._check_block(registry_id, payload.block_id)
        options = self._clean_options(payload.field_type, payload.options)
        key = self._unique_key(payload.key or payload.label, {f.field_key for f in existing}, explicit=bool(payload.key))
        self.repo.add(CustomRegistryField(
            registry_id=registry_id, block_id=payload.block_id, field_key=key, label=payload.label.strip(),
            field_type=payload.field_type, required=payload.required,
            multiple=payload.multiple and payload.field_type in ("counterparty", "user", "object"),
            options=options, show_in_list=payload.show_in_list, sort_order=max([f.sort_order for f in existing], default=-1) + 1,
        ))
        self._log(registry_id, None, user_id, "field_created", f"Добавлено поле «{payload.label.strip()}» ({TYPE_LABELS[payload.field_type]}{', обязательное' if payload.required else ''})")
        self.repo.commit()
        return self._registry_view(registry_id, user_id)

    def update_field(self, field_id: int, payload: FieldUpdate, user_id: str) -> dict:
        field = self._field_row(field_id)
        self._require(user_id, field.registry_id, "can_edit_structure")
        updates = payload.model_dump(exclude_unset=True)
        before = self._field(field)
        new_type = updates.get("field_type", field.field_type)
        if new_type != field.field_type and self.repo.count_field_values(field.id):
            _fail("В поле уже есть значения: тип менять нельзя. Создайте новое поле", status.HTTP_409_CONFLICT)
        if "block_id" in updates:
            self._check_block(field.registry_id, updates["block_id"])
            field.block_id = updates["block_id"]
        if "label" in updates and updates["label"]:
            field.label = updates["label"].strip()
        for attr in ("required", "show_in_list"):
            if updates.get(attr) is not None:
                setattr(field, attr, updates[attr])
        type_changed = new_type != field.field_type
        field.field_type = new_type
        if "multiple" in updates and updates["multiple"] is not None:
            field.multiple = updates["multiple"] and new_type in ("counterparty", "user", "object")
        elif type_changed:
            field.multiple = False
        if "options" in updates or type_changed:
            field.options = self._clean_options(new_type, updates.get("options", field.options))
        after = self._field(field)
        changes = [{"key": k, "old": before[k], "new": after[k]} for k in ("label", "type", "required", "multiple", "options", "show_in_list", "block_id") if before[k] != after[k]]
        if changes:
            self._log(field.registry_id, None, user_id, "field_updated", f"Изменено поле «{before['label']}»: " + ", ".join(c["key"] for c in changes), changes)
        self.repo.commit()
        return self._registry_view(field.registry_id, user_id)

    def delete_field(self, field_id: int, user_id: str, force: bool) -> dict:
        field = self._field_row(field_id)
        self._require(user_id, field.registry_id, "can_edit_structure")
        count = self.repo.count_field_values(field.id)
        if count and not force:
            _fail(f"Поле заполнено в {count} записях. Значения будут удалены: повторите запрос с force=true", status.HTTP_409_CONFLICT)
        registry_id = field.registry_id
        self._log(registry_id, None, user_id, "field_deleted", f"Удалено поле «{field.label}»" + (f" вместе со значениями в {count} записях" if count else ""))
        self.repo.delete(field)
        self.repo.commit()
        return self._registry_view(registry_id, user_id)

    def update_layout(self, registry_id: int, payload: LayoutUpdate, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_edit_structure")
        blocks = {b.id: b for b in self.repo.get_blocks(registry_id)}
        fields = {f.id: f for f in self.repo.get_fields(registry_id)}
        for i, bid in enumerate(payload.blocks or []):
            if bid not in blocks:
                _fail(f"Блок {bid} не из этого реестра", status.HTTP_404_NOT_FOUND)
            blocks[bid].sort_order = i
        for i, item in enumerate(payload.fields or []):
            if item.id not in fields:
                _fail(f"Поле {item.id} не из этого реестра", status.HTTP_404_NOT_FOUND)
            if item.block_id is not None and item.block_id not in blocks:
                _fail(f"Блок {item.block_id} не из этого реестра", status.HTTP_404_NOT_FOUND)
            fields[item.id].sort_order = i
            fields[item.id].block_id = item.block_id
        self._log(registry_id, None, user_id, "layout_updated", "Изменён порядок блоков и полей")
        self.repo.commit()
        return self._registry_view(registry_id, user_id)

    # ---- records --------------------------------------------------------------------
    def list_records(self, registry_id: int, q: str | None, limit: int, offset: int, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_view")
        fields = self.repo.get_fields(registry_id)
        total, rows = self.repo.list_records(registry_id, q, limit, offset)
        values = self.repo.get_values([r.id for r in rows])
        ctx = self._display_context(fields, values)
        files = self.repo.files_counts([r.id for r in rows])
        items = [{**self._record(r, fields, values.get(r.id, {}), ctx), "files_count": files.get(r.id, 0)} for r in rows]
        return {"total": total, "limit": limit, "offset": offset,
                "list_columns": [f.field_key for f in fields if f.show_in_list], "items": items}

    def get_record(self, record_id: int, user_id: str) -> dict:
        self._require(user_id, self._record_row(record_id).registry_id, "can_view")
        return self._record_view(record_id)

    def _record_view(self, record_id: int) -> dict:
        record = self._record_row(record_id)
        fields = self.repo.get_fields(record.registry_id)
        values = self.repo.get_values([record.id])
        ctx = self._display_context(fields, values)
        result = self._record(record, fields, values.get(record.id, {}), ctx, with_blocks=True)
        result["files"] = self.get_files(record_id)
        result["files_count"] = len(result["files"])
        return result

    def create_record(self, registry_id: int, payload: RecordValues, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_add_records")
        fields = self.repo.get_fields(registry_id)
        clean = self._validate(fields, payload.values, {})
        try:
            record = self.repo.add(CustomRegistryRecord(registry_id=registry_id, created_by=user_id))
            self._store(record.id, fields, clean)
            self._log(registry_id, record.id, user_id, "record_created", "Запись добавлена")
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        return self._record_view(record.id)

    def update_record(self, record_id: int, payload: RecordValues, user_id: str) -> dict:
        record = self._record_row(record_id)
        self._require(user_id, record.registry_id, "can_edit_records")
        fields = self.repo.get_fields(record.registry_id)
        current = {fid: v.value for fid, v in self.repo.get_values([record.id]).get(record.id, {}).items()}
        clean = self._validate(fields, payload.values, current)
        old_display = self._record_view(record_id)["display"]
        try:
            self._store(record.id, fields, clean)
            self.repo.touch(record, user_id)
            self.repo.db.flush()
            self.repo.db.expire_all()
            new_display = self._record_view(record_id)["display"]
            labels = {f.field_key: f.label for f in fields}
            changes = [{"key": k, "label": labels[k], "old": old_display.get(k), "new": new_display.get(k)}
                       for k in labels if old_display.get(k) != new_display.get(k)]
            if changes:
                self._log(record.registry_id, record.id, user_id, "record_updated", "Изменено: " + ", ".join(c["label"] for c in changes), changes)
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        return self._record_view(record_id)

    def delete_record(self, record_id: int, user_id: str) -> None:
        record = self._record_row(record_id)
        self._require(user_id, record.registry_id, "can_delete_records")
        paths = [f.file_path for f in self.repo.get_files(record_id)]
        self._log(record.registry_id, record.id, user_id, "record_deleted", "Запись удалена")
        DocumentsLinkRepository(self.repo.db).delete_for_document("registry_record", str(record.id))
        self.repo.delete(record)
        self.repo.commit()
        for path in paths:
            self._remove_from_disk(path)

    # ---- files ----------------------------------------------------------------------
    def upload_files(self, record_id: int, files: list[UploadFile], user_id: str) -> list[dict]:
        record = self._record_row(record_id)
        self._require(user_id, record.registry_id, "can_manage_files")
        Path(CUSTOM_REGISTRY_FILES_DIR).mkdir(parents=True, exist_ok=True)
        created = []
        for upload in files:
            ext = Path(upload.filename or "file").suffix
            storage_name = f"{uuid.uuid4()}{ext}"
            path = f"{CUSTOM_REGISTRY_FILES_DIR}/{storage_name}"
            content = upload.file.read()
            with open(path, "wb") as out:
                out.write(content)
            row = self.repo.add(CustomRegistryFile(
                id=str(uuid.uuid4()), record_id=record_id, original_name=upload.filename or storage_name,
                storage_name=storage_name, extension=ext.lstrip("."), file_path=path, size=len(content), uploaded_by=user_id,
            ))
            self._log(record.registry_id, record_id, user_id, "file_added", f"Загружен файл: {row.original_name}")
            created.append(row)
        self.repo.commit()
        users = self._users([user_id])
        return [self._file(f, users) for f in created]

    def get_files(self, record_id: int, user_id: str | None = None) -> list[dict]:
        registry_id = self._record_row(record_id).registry_id
        if user_id is not None:
            self._require(user_id, registry_id, "can_view")
        rows = self.repo.get_files(record_id)
        users = self._users([r.uploaded_by for r in rows])
        return [self._file(r, users) for r in rows]

    def get_file_path(self, file_id: str, user_id: str) -> tuple[str, str]:
        row = self._file_row(file_id)
        self._require(user_id, self._record_row(row.record_id).registry_id, "can_view")
        if not row.file_path or not os.path.exists(row.file_path):
            _fail("Файл не найден на диске", status.HTTP_404_NOT_FOUND)
        return row.file_path, row.original_name

    def get_preview(self, file_id: str, user_id: str) -> str:
        path, _name = self.get_file_path(file_id, user_id)
        ext = Path(path).suffix.lower()
        if ext == ".pdf":
            return path
        if ext not in PREVIEW_EXTENSIONS:
            _fail("Предпросмотр для этого типа файла не поддерживается", status.HTTP_400_BAD_REQUEST)
        cached = Path(path).parent / f"{Path(path).name}.preview.pdf"
        if not cached.exists():
            result = subprocess.run(["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), path],
                                    capture_output=True, text=True, timeout=120)
            produced = cached.parent / f"{Path(path).stem}.pdf"
            if result.returncode != 0 or not produced.exists():
                _fail("Не удалось построить предпросмотр", status.HTTP_500_INTERNAL_SERVER_ERROR)
            os.rename(str(produced), str(cached))
        return str(cached)

    def delete_file(self, file_id: str, user_id: str) -> None:
        row = self._file_row(file_id)
        record = self._record_row(row.record_id)
        self._require(user_id, record.registry_id, "can_manage_files")
        self._log(record.registry_id, record.id, user_id, "file_deleted", f"Удалён файл: {row.original_name}")
        path = row.file_path
        self.repo.delete(row)
        self.repo.commit()
        self._remove_from_disk(path)

    # ---- history --------------------------------------------------------------------
    def get_record_history(self, record_id: int, limit: int, offset: int, user_id: str) -> dict:
        """Works for deleted records too: their history stays."""
        record = self.repo.get_record(record_id)
        registry_id = record.registry_id if record else self.repo.history_registry_of_record(record_id)
        if registry_id is not None:
            self._require(user_id, registry_id, "can_view")
        elif not self._perms(user_id)["admin"]:
            _fail(NO_RIGHTS["can_view"], status.HTTP_403_FORBIDDEN)
        total, rows = self.repo.get_history(None, record_id, limit, offset)
        return self._history(total, rows, limit, offset)

    def get_registry_history(self, registry_id: int, limit: int, offset: int, user_id: str) -> dict:
        self._require(user_id, registry_id, "can_view")
        total, rows = self.repo.get_history(registry_id, None, limit, offset)
        return self._history(total, rows, limit, offset)

    def _history(self, total: int, rows, limit: int, offset: int) -> dict:
        users = self._users([r.user_id for r in rows])
        return {"total": total, "limit": limit, "offset": offset, "items": [
            {"id": r.id, "registry_id": r.registry_id, "record_id": r.record_id, "action": r.action, "message": r.message,
             "changes": r.changes, "created_at": r.created_at, "user_id": r.user_id, "user": users.get(r.user_id)} for r in rows]}

    def _log(self, registry_id: int, record_id: int | None, user_id: str, action: str, message: str, changes: list | None = None) -> None:
        self.repo.add_history(registry_id, record_id, user_id, action, message, changes)

    def _users(self, ids: list[str]) -> dict:
        if not self.auth_user_repo or not ids:
            return {}
        out = {}
        for u in self.auth_user_repo.get_by_ids(list(set(ids))):
            out[u.id] = {"id": u.id, "short_fio": self._fio(u) or ""}
        return out

    @staticmethod
    def _file(row, users: dict) -> dict:
        return {"id": row.id, "record_id": row.record_id, "original_name": row.original_name, "extension": row.extension,
                "size": row.size, "uploaded_by": row.uploaded_by, "uploaded_by_user": users.get(row.uploaded_by), "uploaded_at": row.uploaded_at}

    @staticmethod
    def _remove_from_disk(path: str | None) -> None:
        try:
            if path and os.path.exists(path):
                os.remove(path)
        except OSError:
            pass

    def _file_row(self, file_id: str) -> CustomRegistryFile:
        row = self.repo.get_file(file_id)
        if not row:
            _fail("Файл не найден", status.HTTP_404_NOT_FOUND)
        return row

    # ---- validation -----------------------------------------------------------------
    def _validate(self, fields: list[CustomRegistryField], given: dict, current: dict[int, object]) -> dict[int, object]:
        """Returns {field_id: stored_value|None} for the fields touched by `given`; checks required over the merged result."""
        by_key = {f.field_key: f for f in fields}
        problems = [{"key": k, "problem": "unknown_field"} for k in given if k not in by_key]
        result: dict[int, object] = {}
        for key, raw in given.items():
            field = by_key.get(key)
            if not field:
                continue
            if _empty(raw):
                result[field.id] = None
                continue
            try:
                result[field.id] = self._coerce(field, raw)
            except ValueError as exc:
                problems.append({"key": key, "label": field.label, "problem": "invalid", "message": str(exc)})
        merged = {**current, **result}
        reported = {p["key"] for p in problems}
        for f in fields:
            if f.required and f.field_key not in reported and _empty(merged.get(f.id)):
                problems.append({"key": f.field_key, "label": f.label, "problem": "required", "message": "Обязательное поле"})
        if problems:
            _fail("Не удалось сохранить запись", problems=problems)
        return result

    def _coerce(self, field: CustomRegistryField, raw):
        t = field.field_type
        if t in ("text", "textarea"):
            if not isinstance(raw, str):
                raise ValueError("Нужна строка")
            text, limit = raw.strip(), MAX_TEXT if t == "text" else MAX_TEXTAREA
            if len(text) > limit:
                raise ValueError(f"Не длиннее {limit} символов")
            return text
        if t in ("number", "money"):
            if isinstance(raw, bool) or not isinstance(raw, (int, float, str)):
                raise ValueError("Нужно число")
            try:
                num = float(str(raw).replace(" ", "").replace(",", "."))
            except ValueError:
                raise ValueError("Нужно число")
            if not math.isfinite(num):
                raise ValueError("Нужно число")
            if t == "money":
                return round(num, 2)
            return int(num) if num == int(num) else num
        if t == "date":
            try:
                return date.fromisoformat(str(raw)[:10]).isoformat()
            except ValueError:
                raise ValueError("Дата в формате ГГГГ-ММ-ДД")
        if t == "boolean":
            if not isinstance(raw, bool):
                raise ValueError("Нужно true или false")
            return raw
        if t == "select":
            if raw not in (field.options or []):
                raise ValueError("Значения нет в списке вариантов")
            return raw
        if t == "multiselect":
            items = raw if isinstance(raw, list) else [raw]
            bad = [i for i in items if i not in (field.options or [])]
            if bad:
                raise ValueError(f"Нет в списке вариантов: {', '.join(map(str, bad))}")
            return list(dict.fromkeys(items))
        # counterparty / user / object: один или несколько (multiple)
        items = raw if isinstance(raw, list) else [raw]
        if not field.multiple and len(items) > 1:
            raise ValueError("В это поле можно выбрать только одно значение")
        items = [self._ref(t, i) for i in items]
        self._check_refs(t, items)
        items = list({(i["object_id"], i["object_type"]) if isinstance(i, dict) else i: i for i in items}.values())
        return items if field.multiple else items[0]

    @staticmethod
    def _ref(kind: str, item):
        if kind == "object":
            if not (isinstance(item, dict) and item.get("object_id") and item.get("object_type") in ("object", "object_levels_id")):
                raise ValueError('Объект: {"object_id": "...", "object_type": "object"|"object_levels_id"}')
            return {"object_id": str(item["object_id"]), "object_type": item["object_type"]}
        if not isinstance(item, str) or not item:
            raise ValueError("Нужен id")
        return item

    def _check_refs(self, kind: str, items: list) -> None:
        if kind == "counterparty" and self.reference_repo:
            names = self.reference_repo.get_counterparty_names(items)
            missing = [i for i in items if i not in names]
            if missing:
                raise ValueError(f"Компания не найдена: {', '.join(missing)}")
        elif kind == "user" and self.auth_user_repo:
            found = {u.id for u in self.auth_user_repo.get_by_ids(items)}
            missing = [i for i in items if i not in found]
            if missing:
                raise ValueError(f"Пользователь не найден: {', '.join(missing)}")
        elif kind == "object" and self.reference_repo:
            missing = [i["object_id"] for i in items if not self._object_name(i["object_id"], i["object_type"])]
            if missing:
                raise ValueError(f"Объект не найден: {', '.join(missing)}")

    def _store(self, record_id: int, fields: list[CustomRegistryField], clean: dict[int, object]) -> None:
        existing = self.repo.get_values([record_id]).get(record_id, {})
        by_id = {f.id: f for f in fields}
        ctx = self._display_context(fields, {record_id: {fid: CustomRegistryValue(record_id=record_id, field_id=fid, value=v) for fid, v in clean.items() if v is not None}})
        for fid, value in clean.items():
            row = existing.get(fid)
            if value is None:
                if row:
                    self.repo.delete(row)
                continue
            text = self._search_text(self._display(by_id[fid], value, ctx))
            if row:
                row.value, row.search_text = value, text
            else:
                self.repo.add(CustomRegistryValue(record_id=record_id, field_id=fid, value=value, search_text=text))
        self.repo.db.flush()

    # ---- display --------------------------------------------------------------------
    def _display_context(self, fields: list[CustomRegistryField], values: dict[int, dict]) -> dict:
        kinds = {f.id: f.field_type for f in fields}
        cps: set[str] = set()
        users: set[str] = set()
        for per_record in values.values():
            for fid, v in per_record.items():
                items = v.value if isinstance(v.value, list) else [v.value]
                if kinds.get(fid) == "counterparty":
                    cps.update(i for i in items if isinstance(i, str))
                elif kinds.get(fid) == "user":
                    users.update(i for i in items if isinstance(i, str))
        cp_names = self.reference_repo.get_counterparty_names(list(cps)) if cps and self.reference_repo else {}
        user_map = {u.id: u for u in self.auth_user_repo.get_by_ids(list(users))} if users and self.auth_user_repo else {}
        return {"counterparties": cp_names, "users": user_map}

    def _display(self, field: CustomRegistryField, value, ctx: dict):
        t = field.field_type
        if value is None:
            return None
        if t == "counterparty":
            names = [ctx["counterparties"].get(i) for i in (value if isinstance(value, list) else [value])]
            return names if field.multiple else names[0]
        if t == "user":
            names = [self._fio(ctx["users"].get(i)) for i in (value if isinstance(value, list) else [value])]
            return names if field.multiple else names[0]
        if t == "object":
            names = [self._object_name(i["object_id"], i["object_type"]) for i in (value if isinstance(value, list) else [value])]
            return names if field.multiple else names[0]
        if t == "boolean":
            return "Да" if value else "Нет"
        return value

    @staticmethod
    def _search_text(display) -> str:
        if isinstance(display, list):
            return "; ".join(str(d) for d in display if d is not None)
        return "" if display is None else str(display)

    @staticmethod
    def _fio(user) -> str | None:
        if not user:
            return None
        surname, name, patr = (getattr(user, a, "") or "" for a in ("surname", "name", "patronymic"))
        return f"{surname} {name[0]}.{patr[0]}." if surname and name and patr else (surname or name or None)

    def _object_name(self, object_id: str, object_type: str) -> str | None:
        if not self.reference_repo:
            return None
        if object_type == "object":
            objs = self.reference_repo.get_objects_by_ids([object_id])
            return (objs[0].short_name or objs[0].full_name) if objs else None
        return self.reference_repo.resolve_object_name(object_id)

    def _record(self, record, fields, vals: dict, ctx: dict, with_blocks: bool = False) -> dict:
        values, display = {}, {}
        for f in fields:
            v = vals.get(f.id)
            values[f.field_key] = v.value if v else None
            display[f.field_key] = self._display(f, v.value, ctx) if v else None
        out = {"id": record.id, "registry_id": record.registry_id, "values": values, "display": display,
               "created_at": record.created_at, "created_by": record.created_by,
               "updated_at": record.updated_at, "updated_by": record.updated_by}
        if with_blocks:
            blocks = {b.id: b for b in self.repo.get_blocks(record.registry_id)}
            grouped: dict[int | None, list] = {}
            for f in fields:
                grouped.setdefault(f.block_id, []).append({**self._field(f), "value": values[f.field_key], "display": display[f.field_key]})
            out["blocks"] = [{"id": b.id, "name": b.name, "fields": grouped.get(b.id, [])} for b in blocks.values()]
            if grouped.get(None):
                out["blocks"].append({"id": None, "name": "Без блока", "fields": grouped[None]})
        return out

    # ---- helpers --------------------------------------------------------------------
    @staticmethod
    def _field(f: CustomRegistryField) -> dict:
        return {"id": f.id, "block_id": f.block_id, "key": f.field_key, "label": f.label, "type": f.field_type,
                "type_label": TYPE_LABELS[f.field_type], "required": bool(f.required), "multiple": bool(f.multiple),
                "options": f.options, "show_in_list": bool(f.show_in_list), "sort_order": f.sort_order}

    @staticmethod
    def _clean_options(field_type: str, options: list[str] | None) -> list[str] | None:
        if field_type not in ("select", "multiselect"):
            return None
        cleaned = list(dict.fromkeys(o.strip() for o in (options or []) if o and o.strip()))
        if not cleaned:
            _fail("Для выбора из списка укажите варианты (options)")
        return cleaned

    @staticmethod
    def _unique_key(source: str, taken: set[str], explicit: bool) -> str:
        if explicit and not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", source):
            _fail("key: латиница в нижнем регистре, цифры и _, начинается с буквы")
        if explicit and source in taken:
            _fail("Поле с таким key уже есть", status.HTTP_409_CONFLICT)
        if explicit:
            return source
        base = re.sub(r"[^a-z0-9]+", "_", "".join(TRANSLIT.get(ch, ch) for ch in source.lower())).strip("_")[:50] or "field"
        if not base[0].isalpha():
            base = "f_" + base
        key, n = base, 2
        while key in taken:
            key, n = f"{base}_{n}", n + 1
        return key

    def _check_block(self, registry_id: int, block_id: int | None) -> None:
        if block_id is not None:
            block = self.repo.get_block(block_id)
            if not block or block.registry_id != registry_id:
                _fail("Блок не найден в этом реестре", status.HTTP_404_NOT_FOUND)

    def _registry(self, registry_id: int) -> CustomRegistry:
        row = self.repo.get_registry(registry_id)
        if not row:
            _fail("Реестр не найден", status.HTTP_404_NOT_FOUND)
        return row

    def _block(self, block_id: int) -> CustomRegistryBlock:
        row = self.repo.get_block(block_id)
        if not row:
            _fail("Блок не найден", status.HTTP_404_NOT_FOUND)
        return row

    def _field_row(self, field_id: int) -> CustomRegistryField:
        row = self.repo.get_field(field_id)
        if not row:
            _fail("Поле не найдено", status.HTTP_404_NOT_FOUND)
        return row

    def _record_row(self, record_id: int) -> CustomRegistryRecord:
        row = self.repo.get_record(record_id)
        if not row:
            _fail("Запись не найдена", status.HTTP_404_NOT_FOUND)
        return row
