import os
import subprocess
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status

from app.models.task import (
    Task,
    TaskAccomplishment,
    TaskAccomplishmentCreate,
    TaskAccomplishmentUpdate,
    TaskBoard,
    TaskBoardColumn,
    TaskBoardColumnCreate,
    TaskBoardColumnUpdate,
    TaskBoardCreate,
    TaskBoardUpdate,
    TaskBoardUserRole,
    TaskBoardUserRoleCreate,
    TaskBoardUserRoleUpdate,
    TaskCreate,
    TaskFile,
    TaskItem,
    TaskItemCreate,
    TaskItemUpdate,
    TaskResult,
    TaskResultCreate,
    TaskResultUpdate,
    TaskTag,
    TaskTagCreate,
    TaskTagUpdate,
    TaskUpdate,
    TaskUserRole,
    TaskUserRoleCreate,
    TaskUserRoleUpdate,
    msk_now,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.task_repository import TaskRepository
from app.repositories.vk_repository import VkRepository
from app.services.vk_service import VkService
from app.services.ws_manager import ws_manager

BASE_TASK_FILES_DIR = "/home/webserver/models/supply/tasks"


class TaskService:
    def __init__(
        self,
        repo: TaskRepository,
        auth_user_repo: AuthUserRepository | None = None,
        reference_repo: ReferenceObjectRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    def _get_users_map(self, user_ids: list[str]):
        if not self.auth_user_repo:
            return {}
        users = self.auth_user_repo.get_by_ids([uid for uid in user_ids if uid])
        return {user.id: user for user in users}

    @staticmethod
    def _map_user(user):
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        short_fio = " ".join(part for part in [user.surname, name_initial, patronymic_initial] if part).strip()
        return {
            "id": user.id,
            "name": user.name,
            "surname": user.surname,
            "patronymic": user.patronymic,
            "short_fio": short_fio,
        }

    @staticmethod
    @staticmethod
    def _serialize_log(row, users_by_id: dict | None = None):
        return {
            "id": row.id,
            "log_object_id": row.log_object_id,
            "log_object_type": row.log_object_type,
            "message": row.message,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": TaskService._map_user((users_by_id or {}).get(row.created_by)),
        }

    def _build_vk_task_text(self, task, actor_fio: str | None = None, header: str = "Новая задача") -> str:
        lines = [f"{header}\n"]
        if task.name:
            lines.append(f"Название: {task.name}")
        if task.description:
            desc = task.description[:200]
            if len(task.description) > 200:
                desc += "…"
            lines.append(f"Описание: {desc}")
        if actor_fio:
            lines.append(f"Постановщик: {actor_fio}")
        else:
            creator_fio = self._get_user_fio(task.created_by)
            lines.append(f"Постановщик: {creator_fio}")
        lines.append(f"\nСсылка: https://supply.st29.ru/tasks")
        return "\n".join(lines)

    def _send_vk_notification(self, user_id: str, message: str) -> None:
        try:
            vk_repo = VkRepository(self.repo.db)
            service = VkService(vk_repo)
            vk_id = service.get_vk_id(user_id)
            if vk_id:
                service.send_notification(vk_id, message)
        except Exception:
            pass

    def _send_vk_task_notification(self, user_id: str, task, actor_fio: str | None = None, header: str = "Новая задача") -> None:
        message = self._build_vk_task_text(task, actor_fio, header)
        self._send_vk_notification(user_id, message)

    def _get_user_fio(self, user_id: str) -> str:
        if not self.auth_user_repo or not user_id:
            return user_id
        users = self._get_users_map([user_id])
        user = self._map_user(users.get(user_id))
        return user["short_fio"] if user else user_id

    def _get_task_user_ids(self, task_id: str) -> list[str]:
        row = self.repo.get_task_by_id(task_id)
        if not row:
            return []
        ids = {row.created_by}
        for r in self.repo.get_user_roles(task_id=task_id):
            ids.add(r.user_id)
        return list(ids)

    def _get_board_user_ids(self, board_id: str) -> list[str]:
        row = self.repo.get_board_by_id(board_id)
        if not row:
            return []
        ids = {row.created_by}
        for r in self.repo.get_board_user_roles(task_boards_id=board_id):
            ids.add(r.user_id)
        return list(ids)

    def _notify_task_log(self, task_id: str, message: str, actor_user_id: str) -> None:
        user_ids = self._get_task_user_ids(task_id)
        actor_fio = self._get_user_fio(actor_user_id)
        ws_manager.send_task_log(user_ids, {
            "id": str(uuid.uuid4()),
            "log_object_id": task_id,
            "log_object_type": "task",
            "message": message,
            "full_log": message,
            "created_at": msk_now().isoformat(),
            "created_by": actor_user_id,
            "created_by_user": {"id": actor_user_id, "short_fio": actor_fio},
        })

    def _notify_incomplete_count(self, user_id: str) -> None:
        count = self.repo.count_incomplete_tasks(user_id)
        ws_manager.send_incomplete_count(user_id, count)

    def _resolve_object_name(self, row) -> str | None:
        return self._resolve_entity_name(row.object_id, row.object_type)

    def _resolve_entity_name(self, object_id: str | None, object_type: str | None) -> str | None:
        if not self.reference_repo or not object_id or not object_type:
            return None
        if object_type == "object_id":
            objs = self.reference_repo.get_objects_by_ids([object_id])
            if objs:
                return objs[0].short_name or objs[0].full_name
            return None
        elif object_type == "object_levels_id":
            from app.services.project_name_builder import build_project_name, load_project_reference_maps
            levels_by_id, objects_by_id, contracts_by_id, work_types_by_id = load_project_reference_maps(
                self.reference_repo, [object_id]
            )
            return build_project_name(object_id, levels_by_id, objects_by_id, contracts_by_id, work_types_by_id)
        return None

    def _resolve_connection_name(self, connection_id: str | None, connection_type: str | None) -> str | None:
        if not connection_id or not connection_type:
            return None

        if connection_type == "task-columns":
            col = self.repo.get_board_column_by_id(connection_id)
            if not col:
                return None
            board = self.repo.get_board_by_id(col.task_board_id) if col.task_board_id else None
            if not board:
                return col.name
            obj_name = self._resolve_entity_name(board.object_id, board.object_type)
            return " - ".join(p for p in [obj_name, board.name, col.name] if p)

        elif connection_type == "letter":
            letter = self.repo.get_letter_by_id(int(connection_id))
            if not letter:
                return None
            prefix = "Исходящее письмо" if letter.type == "outgoing" else "Входящее письмо"
            parts = [prefix]
            if letter.name:
                parts.append(letter.name)
            if letter.num:
                parts.append(f"№ {letter.num}")
            return " ".join(parts)

        elif connection_type == "contract":
            contract = self.repo.get_contract_by_id(int(connection_id))
            if not contract:
                return None
            doc_type_name = self.repo.get_document_type_name(contract.document_type_id) or ""
            name_part = doc_type_name or contract.name or ""
            if contract.num:
                return f"{name_part} № {contract.num}" if name_part else f"№ {contract.num}"
            return name_part or "Договор"

        elif connection_type == "request":
            req = self.repo.get_request_by_id(int(connection_id))
            if not req:
                return None
            return req.name or "Заявка"

        elif connection_type == "invoice":
            inv = self.repo.get_invoice_by_id(int(connection_id))
            if not inv:
                return None
            return f"Счет № {inv.num}" if inv.num else "Счет"

        elif connection_type == "deal":
            deal = self.repo.get_deal_by_id(connection_id)
            if not deal:
                return None
            return deal.name or ""

        elif connection_type == "warehouse":
            wh = self.repo.get_warehouse_by_id(connection_id)
            if not wh:
                return None
            return wh.name or ""

        elif connection_type == "specification":
            spec = self.repo.get_specification_by_id(connection_id)
            if not spec:
                return None
            obj_name = self._resolve_entity_name(spec.object_levels_id, "object_levels_id") if spec.object_levels_id else None
            if obj_name:
                return f"{obj_name} - {spec.name}" if spec.name else obj_name
            return spec.name or ""

        return None

    # --- Logs ---

    def get_logs(self, log_object_id: str | None = None, created_by: str | None = None) -> list[dict]:
        rows = self.repo.get_logs(log_object_id, created_by)
        user_ids = {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_log(r, users_by_id) for r in rows]

    # --- Task ---

    def _serialize_task(self, row: Task) -> dict:
        user_ids = {row.created_by}
        user_roles = self.repo.get_user_roles(task_id=row.id)
        for ur in user_roles:
            user_ids.add(ur.user_id)
            user_ids.add(ur.created_by)

        users_by_id = self._get_users_map(list(user_ids))

        task_board_id = None
        if row.connection_type == "task-columns" and row.connection_id:
            col = self.repo.get_board_column_by_id(row.connection_id)
            task_board_id = col.task_board_id if col else None

        return {
            "id": row.id,
            "connection_id": row.connection_id,
            "connection_type": row.connection_type,
            "connection_name": self._resolve_connection_name(row.connection_id, row.connection_type),
            "task_board_id": task_board_id,
            "name": row.name,
            "description": row.description,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": self._resolve_object_name(row),
            "urgent": row.urgent,
            "date_start": row.date_start.strftime("%d.%m.%Y %H:%M") if row.date_start else None,
            "date_end": row.date_end.strftime("%d.%m.%Y %H:%M") if row.date_end else None,
            "date_completed": row.date_completed.strftime("%d.%m.%Y %H:%M") if row.date_completed else None,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "status_id": row.status_id,
            "status_name": self.repo.get_status_name(row.status_id),
            "chat_id": self.repo.get_chat_id_by_task_id(row.id),
            "vertical_num": row.vertical_num,
            "items": [self._serialize_item(r, users_by_id) for r in self.repo.get_items(task_id=row.id)],
            "user_roles": [self._serialize_user_role(ur, users_by_id) for ur in user_roles],
            "results": [self._serialize_result(r) for r in self.repo.get_results(task_id=row.id)],
            "files": [self._serialize_file(r) for r in self.repo.get_files(task_id=row.id)],
            "tags": [self._serialize_tag(r) for r in self.repo.get_tags(task_id=row.id)],
            "accomplishments": [self._serialize_accomplishment(r) for r in self.repo.get_accomplishments(task_id=row.id)],
        }

    def get_tasks(self, connection_type: str | None = None, connection_id: str | None = None) -> list[dict]:
        if connection_type and connection_id:
            rows = self.repo.get_tasks_by_connection(connection_id, connection_type)
        else:
            rows = self.repo.get_tasks()
        return [self._serialize_task(r) for r in rows]

    def get_my_tasks(self, user_id: str, role: str | None = None) -> list[dict]:
        ids = self.repo.get_task_ids_by_user(user_id, role)
        if not ids:
            return []
        all_tasks = self.repo.get_tasks()
        rows = [r for r in all_tasks if r.id in ids]
        return [self._serialize_task(r) for r in rows]

    def get_task(self, task_id: str) -> dict:
        row = self.repo.get_task_by_id(task_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        return self._serialize_task(row)

    def get_incomplete_count(self, user_id: str) -> int:
        return self.repo.count_incomplete_tasks(user_id)

    def create_task(self, payload: TaskCreate, created_by: str) -> dict:
        data = payload.model_dump(exclude_none=True)
        data["created_by"] = created_by
        if "status_id" not in data or not data.get("status_id"):
            data["status_id"] = "e0896c9d-7646-11f1-b481-bc241127d0bd"
        created = self.repo.create_task(data)
        serialized = self._serialize_task(created)
        actor_fio = self._get_user_fio(created_by)
        msg = f"{actor_fio} создал задачу {created.name}"
        self.repo.create_log(created.id, msg, created_by)
        user_ids = self._get_task_user_ids(created.id)
        ws_manager.send_task_created(user_ids, serialized)
        self._notify_task_log(created.id, msg, created_by)
        self._notify_incomplete_count(created_by)

        # VK: notify all board participants about new task
        if created.connection_type == "task-columns" and created.connection_id:
            col = self.repo.get_board_column_by_id(created.connection_id)
            if col and col.task_board_id:
                board = self.repo.get_board_by_id(col.task_board_id)
                if board:
                    board_users = self._get_board_user_ids(board.id)
                    for uid in board_users:
                        if uid != created_by:
                            self._send_vk_task_notification(uid, created, actor_fio)

        return serialized

    def update_task(self, task_id: str, payload: TaskUpdate, user_id: str) -> dict:
        row = self.repo.get_task_by_id(task_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")

        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_task(row)

        actor_fio = self._get_user_fio(user_id)
        completed_id = "1ff32c4b-1312-11f1-aa8c-bc241127d0bd"
        resumed_id = "6b4fbf85-7901-11f1-b481-bc241127d0bd"
        messages = []

        if "name" in updates:
            old_val = row.name
            new_val = updates["name"]
            messages.append(f"{actor_fio} поменял название задачи с {old_val} на {new_val}")

        if "description" in updates:
            old_val = row.description
            new_val = updates["description"]
            if not old_val and new_val:
                messages.append(f"{actor_fio} установил описание задачи {new_val}")
            elif old_val and new_val and old_val != new_val:
                messages.append(f"{actor_fio} поменял описание задачи с {old_val} на {new_val}")
            elif old_val and not new_val:
                messages.append(f"{actor_fio} удалил описание задачи")

        if "date_start" in updates:
            old_val = row.date_start
            new_val = updates["date_start"]
            if not old_val and new_val:
                messages.append(f"{actor_fio} установил дату начала задачи")
            elif old_val and new_val and old_val != new_val:
                messages.append(f"{actor_fio} поменял дату начала задачи")
            elif old_val and not new_val:
                messages.append(f"{actor_fio} переместил дату начала задачи")

        if "date_end" in updates:
            old_val = row.date_end
            new_val = updates["date_end"]
            if not old_val and new_val:
                messages.append(f"{actor_fio} установил крайний срок задачи")
            elif old_val and new_val and old_val != new_val:
                messages.append(f"{actor_fio} переместил крайний срок задачи")
            elif old_val and not new_val:
                messages.append(f"{actor_fio} удалил крайний срок задачи")

        if "status_id" in updates:
            old_val = row.status_id
            new_val = updates["status_id"]
            if new_val == completed_id and old_val != completed_id:
                messages.append("Задача завершена")
            elif new_val == resumed_id and old_val == completed_id:
                messages.append("Возобновлено выполнение задачи")

        for key, value in updates.items():
            setattr(row, key, value)
        self.repo.save_task(row)

        serialized = self._serialize_task(row)
        user_ids = self._get_task_user_ids(task_id)
        ws_manager.send_task_updated(user_ids, serialized)

        for msg in messages:
            self.repo.create_log(task_id, msg, user_id)
            self._notify_task_log(task_id, msg, user_id)

        for uid in user_ids:
            self._notify_incomplete_count(uid)

        if "status_id" in updates and updates.get("status_id") == completed_id and row.created_by != user_id:
            self._send_vk_task_notification(row.created_by, row, actor_fio, "Задача завершена")

        return serialized

    def delete_task(self, task_id: str, user_id: str) -> None:
        row = self.repo.get_task_by_id(task_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task not found")
        user_ids = self._get_task_user_ids(task_id)
        self.repo.delete_logs_by_task(task_id)
        self.repo.delete_task(row)
        ws_manager.send_task_deleted(user_ids, task_id)
        for uid in user_ids:
            self._notify_incomplete_count(uid)
        actor_fio = self._get_user_fio(user_id)
        self.repo.create_log(task_id, f"{actor_fio} удалил задачу {row.name}", user_id)

    # --- TaskItem ---

    def _serialize_item(self, row: TaskItem, users_by_id: dict | None = None) -> dict:
        item_roles = self.repo.get_user_roles(task_item_id=row.id)
        if users_by_id is None:
            role_user_ids = {r.user_id for r in item_roles} | {r.created_by for r in item_roles}
            users_by_id = self._get_users_map(list(role_user_ids))
        return {
            "id": row.id,
            "task_id": row.task_id,
            "num": row.num,
            "name": row.name,
            "urgent": row.urgent,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
            "date_start": row.date_start,
            "date_end": row.date_end,
            "status_id": row.status_id,
            "user_roles": [self._serialize_user_role(r, users_by_id) for r in item_roles],
        }

    def get_items(self, task_id: str | None = None) -> list[dict]:
        rows = self.repo.get_items(task_id)
        return [self._serialize_item(r) for r in rows]

    def get_item(self, item_id: str) -> dict:
        row = self.repo.get_item_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task item not found")
        return self._serialize_item(row)

    def create_item(self, payload: TaskItemCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        if "status_id" not in data or not data.get("status_id"):
            data["status_id"] = "e0896c9d-7646-11f1-b481-bc241127d0bd"
        created = self.repo.create_item(data)
        self.repo.create_log(created.task_id, f"добавил пункт {created.name}", created_by)
        return self._serialize_item(created)

    def update_item(self, item_id: str, payload: TaskItemUpdate, user_id: str) -> dict:
        row = self.repo.get_item_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task item not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_item(row)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.repo.save_item(row)
        self.repo.create_log(row.task_id, f"изменил пункт задачи {row.name}", user_id)
        return self._serialize_item(row)

    def delete_item(self, item_id: str, user_id: str) -> None:
        row = self.repo.get_item_by_id(item_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task item not found")
        task_id = row.task_id
        self.repo.delete_item(row)
        self.repo.create_log(task_id, f"удалил пункт задачи {row.name}", user_id)

    # --- TaskUserRole ---

    def _serialize_user_role(self, row: TaskUserRole, users_by_id: dict) -> dict:
        return {
            "id": row.id,
            "task_id": row.task_id,
            "task_item_id": row.task_item_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)) if users_by_id else None,
            "role": row.role,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def get_user_roles(self, task_id: str | None = None, task_item_id: str | None = None) -> list[dict]:
        rows = self.repo.get_user_roles(task_id, task_item_id)
        user_ids = {row.user_id for row in rows} | {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_user_role(r, users_by_id) for r in rows]

    def get_user_role(self, role_id: str) -> dict:
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        users_by_id = self._get_users_map([row.user_id, row.created_by])
        return self._serialize_user_role(row, users_by_id)

    def create_user_role(self, payload: TaskUserRoleCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_user_role(data)
        users_by_id = self._get_users_map([created.user_id, created.created_by])
        user_info = self._map_user(users_by_id.get(created.user_id))
        target_fio = user_info["short_fio"] if user_info else created.user_id
        actor_fio = self._get_user_fio(created_by)
        log_id = created.task_id or created.task_item_id or ""
        if log_id:
            if created.role == "responsible":
                existing = self.repo.get_user_roles(task_id=created.task_id, role="responsible") if created.task_id else []
                if existing:
                    self.repo.create_log(log_id, f"{actor_fio} переназначил исполнителя задачи {target_fio}", created_by)
                else:
                    self.repo.create_log(log_id, f"{actor_fio} назначил исполнителя задачи {target_fio}", created_by)
            elif created.role == "co-executor":
                self.repo.create_log(log_id, f"{actor_fio} назначил соисполнителем задачи {target_fio}", created_by)
            elif created.role == "observer":
                self.repo.create_log(log_id, f"{actor_fio} назначил наблюдателем задачи {target_fio}", created_by)
        if created.task_id:
            task = self.repo.get_task_by_id(created.task_id)
            serialized = self._serialize_task(task)
            user_ids = self._get_task_user_ids(created.task_id)
            ws_manager.send_task_updated(user_ids, serialized)
            self._notify_incomplete_count(created.user_id)
            if created.role in ("responsible", "co-executor") and created.user_id != task.created_by:
                self._send_vk_task_notification(created.user_id, task, actor_fio)
        return self._serialize_user_role(created, users_by_id)

    def update_user_role(self, role_id: str, payload: TaskUserRoleUpdate, user_id: str) -> dict:
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save_user_role(row)
        users_by_id = self._get_users_map([updated.user_id, updated.created_by])
        if "role" in updates:
            log_id = updated.task_id or updated.task_item_id or ""
            if log_id:
                target_fio = self._get_user_fio(updated.user_id)
                actor_fio = self._get_user_fio(user_id)
                new_role = updated.role
                if new_role == "responsible":
                    self.repo.create_log(log_id, f"{actor_fio} назначил исполнителя задачи {target_fio}", user_id)
                elif new_role == "co-executor":
                    self.repo.create_log(log_id, f"{actor_fio} назначил соисполнителем задачи {target_fio}", user_id)
                elif new_role == "observer":
                    self.repo.create_log(log_id, f"{actor_fio} назначил наблюдателем задачи {target_fio}", user_id)
            if updated.task_id:
                serialized = self._serialize_task(self.repo.get_task_by_id(updated.task_id))
                user_ids = self._get_task_user_ids(updated.task_id)
                ws_manager.send_task_updated(user_ids, serialized)
        return self._serialize_user_role(updated, users_by_id)

    def delete_user_role(self, role_id: str, user_id: str) -> None:
        row = self.repo.get_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User role not found")
        log_id = row.task_id or row.task_item_id or ""
        target_fio = self._get_user_fio(row.user_id)
        actor_fio = self._get_user_fio(user_id)
        task_id = row.task_id
        if task_id:
            task = self.repo.get_task_by_id(task_id)
            serialized = self._serialize_task(task) if task else None
        self.repo.delete_user_role(row)
        if log_id:
            if row.role == "co-executor":
                self.repo.create_log(log_id, f"{actor_fio} убрал соисполнителя задачи {target_fio}", user_id)
            elif row.role == "observer":
                self.repo.create_log(log_id, f"{actor_fio} убрал наблюдателя задачи {target_fio}", user_id)
        if task_id and serialized:
            user_ids = self._get_task_user_ids(task_id)
            ws_manager.send_task_updated(user_ids, serialized)
            self._notify_incomplete_count(row.user_id)

    # --- TaskResult ---

    def _serialize_result(self, row: TaskResult) -> dict:
        return {
            "id": row.id,
            "task_id": row.task_id,
            "text": row.text,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def get_results(self, task_id: str | None = None) -> list[dict]:
        rows = self.repo.get_results(task_id)
        return [self._serialize_result(r) for r in rows]

    def get_result(self, result_id: str) -> dict:
        row = self.repo.get_result_by_id(result_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result not found")
        return self._serialize_result(row)

    def create_result(self, payload: TaskResultCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_result(data)
        actor_fio = self._get_user_fio(created_by)
        log_msg = f"{actor_fio} добавил результат работы"
        self.repo.create_log(created.task_id, log_msg, created_by)
        if created.task_id:
            serialized = self._serialize_task(self.repo.get_task_by_id(created.task_id))
            user_ids = self._get_task_user_ids(created.task_id)
            ws_manager.send_task_updated(user_ids, serialized)
            task = self.repo.get_task_by_id(created.task_id)
            if task and task.created_by != created_by:
                self._send_vk_task_notification(task.created_by, task, actor_fio, "Добавлен результат работы")
        return self._serialize_result(created)

    def update_result(self, result_id: str, payload: TaskResultUpdate, user_id: str) -> dict:
        row = self.repo.get_result_by_id(result_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_result(row)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        self.repo.save_result(row)
        self.repo.create_log(row.task_id, f"изменил результат", user_id)
        return self._serialize_result(row)

    def delete_result(self, result_id: str, user_id: str) -> None:
        row = self.repo.get_result_by_id(result_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task result not found")
        task_id = row.task_id
        self.repo.delete_result(row)
        self.repo.create_log(task_id, f"удалил результат", user_id)

    # --- TaskFile ---

    def _serialize_file(self, row: TaskFile) -> dict:
        return {
            "id": row.id,
            "task_id": row.task_id,
            "task_result_id": row.task_result_id,
            "original_name": row.original_name,
            "storage_name": row.storage_name,
            "extension": row.extension,
            "file_path": row.file_path,
            "uploaded_by": row.uploaded_by,
            "uploaded_at": row.uploaded_at,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def get_files(self, task_id: str | None = None, task_result_id: str | None = None) -> list[dict]:
        rows = self.repo.get_files(task_id, task_result_id)
        return [self._serialize_file(r) for r in rows]

    def get_file(self, file_id: str) -> dict:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        return self._serialize_file(row)

    def upload(
        self,
        original_name: str,
        file_bytes: bytes,
        uploaded_by: str,
        task_id: str | None = None,
        task_result_id: str | None = None,
        file_dir: str | None = None,
    ):
        extension = Path(original_name).suffix.lower().lstrip(".")
        storage_name = f"{uuid.uuid4().hex}{('.' + extension) if extension else ''}"
        target_dir = file_dir or (os.path.join(BASE_TASK_FILES_DIR, task_id) if task_id else os.path.join(BASE_TASK_FILES_DIR, "unsorted"))
        os.makedirs(target_dir, exist_ok=True)
        file_path = os.path.join(target_dir, storage_name)

        with open(file_path, "wb") as f:
            f.write(file_bytes)

        created = self.repo.create_file({
            "task_id": task_id,
            "task_result_id": task_result_id,
            "original_name": original_name,
            "storage_name": storage_name,
            "extension": extension or "",
            "file_path": file_path,
            "uploaded_by": uploaded_by,
        })
        log_msg = f"прикрепил файл {original_name} к задаче"
        self.repo.create_log(task_id, log_msg, uploaded_by)
        if task_id:
            serialized = self._serialize_task(self.repo.get_task_by_id(task_id))
            user_ids = self._get_task_user_ids(task_id)
            ws_manager.send_task_updated(user_ids, serialized)
        return self._serialize_file(created)

    def delete_file(self, file_id: str, user_id: str) -> None:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        task_id = row.task_id
        original_name = row.original_name
        if row.file_path and os.path.exists(row.file_path):
            os.remove(row.file_path)
        self.repo.delete_file(row)
        log_msg = f"открепил файл {original_name} задачи"
        self.repo.create_log(task_id, log_msg, user_id)
        if task_id:
            serialized = self._serialize_task(self.repo.get_task_by_id(task_id))
            user_ids = self._get_task_user_ids(task_id)
            ws_manager.send_task_updated(user_ids, serialized)

    def get_download(self, file_id: str) -> tuple[str, str]:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")
        return row.file_path, row.original_name

    PREVIEW_EXTENSIONS = {".docx", ".doc", ".xls", ".xlsx", ".pptx"}

    def get_preview(self, file_id: str) -> str:
        row = self.repo.get_file_by_id(file_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")
        if not row.file_path or not os.path.exists(row.file_path):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found on disk")

        ext = Path(row.file_path).suffix.lower()
        if ext == ".pdf":
            return row.file_path

        if ext not in self.PREVIEW_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Preview not supported for this file type")

        cached = Path(row.file_path).parent / f"{Path(row.file_path).name}.preview.pdf"
        if cached.exists():
            return str(cached)

        result = subprocess.run(
            ["libreoffice", "--headless", "--convert-to", "pdf", "--outdir", str(cached.parent), row.file_path],
            capture_output=True, text=True, timeout=120,
        )
        if result.returncode != 0:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Conversion failed: {result.stderr.strip()}")

        output_name = f"{Path(row.file_path).stem}.pdf"
        output_path = cached.parent / output_name
        if output_path.exists():
            os.rename(str(output_path), str(cached))

        if not cached.exists():
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Conversion produced no output")

        return str(cached)

    # --- TaskBoard ---

    def _serialize_board(self, row: TaskBoard) -> dict:
        user_ids = {row.created_by}
        user_roles = self.repo.get_board_user_roles(task_boards_id=row.id)
        for ur in user_roles:
            user_ids.add(ur.user_id)
            user_ids.add(ur.created_by)

        users_by_id = self._get_users_map(list(user_ids))

        return {
            "id": row.id,
            "name": row.name,
            "object_id": row.object_id,
            "object_type": row.object_type,
            "object_name": self._resolve_object_name(row),
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "columns": [self._serialize_board_column(c) for c in self.repo.get_board_columns(task_board_id=row.id)],
            "user_roles": [self._serialize_board_user_role(ur, users_by_id) for ur in user_roles],
        }

    def get_boards(self) -> list[dict]:
        rows = self.repo.get_boards()
        return [self._serialize_board(r) for r in rows]

    def get_my_boards(self, user_id: str) -> list[dict]:
        ids = self.repo.get_board_ids_by_user(user_id)
        if not ids:
            return []
        all_boards = self.repo.get_boards()
        rows = [r for r in all_boards if r.id in ids]
        return [self._serialize_board(r) for r in rows]

    def get_board(self, board_id: str) -> dict:
        row = self.repo.get_board_by_id(board_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        return self._serialize_board(row)

    def create_board(self, payload: TaskBoardCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_board(data)
        serialized = self._serialize_board(created)
        user_ids = self._get_board_user_ids(created.id)
        ws_manager.send_board_created(user_ids, serialized)
        return serialized

    def update_board(self, board_id: str, payload: TaskBoardUpdate, user_id: str) -> dict:
        row = self.repo.get_board_by_id(board_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_board(row)
        for key, value in updates.items():
            setattr(row, key, value)
        self.repo.save_board(row)
        serialized = self._serialize_board(row)
        user_ids = self._get_board_user_ids(board_id)
        ws_manager.send_board_updated(user_ids, serialized)
        return serialized

    def delete_board(self, board_id: str, user_id: str) -> None:
        row = self.repo.get_board_by_id(board_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        user_ids = self._get_board_user_ids(board_id)
        self.repo.delete_board(row)
        ws_manager.send_board_deleted(user_ids, board_id)

    def get_board_tasks(self, board_id: str, user_id: str | None = None) -> dict:
        row = self.repo.get_board_by_id(board_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board not found")
        board_data = self._serialize_board(row)
        columns = self.repo.get_board_columns(task_board_id=board_id)
        result_columns = []
        for col in columns:
            tasks = self.repo.get_tasks_by_connection(col.id, "task-columns")
            col_data = self._serialize_board_column(col)
            col_data["tasks"] = [self._serialize_task(t) for t in tasks]
            result_columns.append(col_data)
        board_data["columns"] = result_columns
        return board_data

    # --- TaskBoardColumn ---

    def _serialize_board_column(self, row: TaskBoardColumn) -> dict:
        return {
            "id": row.id,
            "task_board_id": row.task_board_id,
            "num": row.num,
            "name": row.name,
            "created_at": row.created_at,
            "created_by": row.created_by,
        }

    def get_board_columns(self, task_board_id: str | None = None) -> list[dict]:
        rows = self.repo.get_board_columns(task_board_id)
        return [self._serialize_board_column(r) for r in rows]

    def get_board_column(self, column_id: str) -> dict:
        row = self.repo.get_board_column_by_id(column_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board column not found")
        return self._serialize_board_column(row)

    def create_board_column(self, payload: TaskBoardColumnCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_board_column(data)
        serialized = self._serialize_board_column(created)
        if created.task_board_id:
            user_ids = self._get_board_user_ids(created.task_board_id)
            ws_manager.send_column_created(user_ids, created.task_board_id, serialized)
        return serialized

    def update_board_column(self, column_id: str, payload: TaskBoardColumnUpdate, user_id: str) -> dict:
        row = self.repo.get_board_column_by_id(column_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board column not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_board_column(row)
        for key, value in updates.items():
            setattr(row, key, value)
        self.repo.save_board_column(row)
        serialized = self._serialize_board_column(row)
        if row.task_board_id:
            user_ids = self._get_board_user_ids(row.task_board_id)
            ws_manager.send_column_updated(user_ids, row.task_board_id, serialized)
        return serialized

    def delete_board_column(self, column_id: str, user_id: str) -> None:
        row = self.repo.get_board_column_by_id(column_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board column not found")
        board_id = row.task_board_id
        self.repo.delete_board_column(row)
        if board_id:
            user_ids = self._get_board_user_ids(board_id)
            ws_manager.send_column_deleted(user_ids, board_id, column_id)

    # --- TaskBoardUserRole ---

    def _serialize_board_user_role(self, row: TaskBoardUserRole, users_by_id: dict) -> dict:
        return {
            "id": row.id,
            "task_boards_id": row.task_boards_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)) if users_by_id else None,
            "role": row.role,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)) if users_by_id else None,
            "updated_at": row.updated_at,
            "updated_by": row.updated_by,
        }

    def get_board_user_roles(self, task_boards_id: str | None = None) -> list[dict]:
        rows = self.repo.get_board_user_roles(task_boards_id)
        user_ids = {row.user_id for row in rows} | {row.created_by for row in rows}
        users_by_id = self._get_users_map(list(user_ids))
        return [self._serialize_board_user_role(r, users_by_id) for r in rows]

    def get_board_user_role(self, role_id: str) -> dict:
        row = self.repo.get_board_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board user role not found")
        users_by_id = self._get_users_map([row.user_id, row.created_by])
        return self._serialize_board_user_role(row, users_by_id)

    def create_board_user_role(self, payload: TaskBoardUserRoleCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_board_user_role(data)
        users_by_id = self._get_users_map([created.user_id, created.created_by])
        return self._serialize_board_user_role(created, users_by_id)

    def update_board_user_role(self, role_id: str, payload: TaskBoardUserRoleUpdate, user_id: str) -> dict:
        row = self.repo.get_board_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board user role not found")
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(row, key, value)
        row.updated_at = msk_now()
        row.updated_by = user_id
        updated = self.repo.save_board_user_role(row)
        users_by_id = self._get_users_map([updated.user_id, updated.created_by])
        return self._serialize_board_user_role(updated, users_by_id)

    def delete_board_user_role(self, role_id: str, user_id: str) -> None:
        row = self.repo.get_board_user_role_by_id(role_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Board user role not found")
        self.repo.delete_board_user_role(row)

    # --- TaskTag ---

    def _serialize_tag(self, row: TaskTag) -> dict:
        return {
            "id": row.id,
            "task_id": row.task_id,
            "tag": row.tag,
            "created_by": row.created_by,
            "created_at": row.created_at,
        }

    def get_tags(self, task_id: str | None = None) -> list[dict]:
        rows = self.repo.get_tags(task_id)
        return [self._serialize_tag(r) for r in rows]

    def get_tag(self, tag_id: str) -> dict:
        row = self.repo.get_tag_by_id(tag_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        return self._serialize_tag(row)

    def create_tag(self, payload: TaskTagCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        created = self.repo.create_tag(data)
        actor_fio = self._get_user_fio(created_by)
        log_msg = f"{actor_fio} добавил тэг к задаче"
        self.repo.create_log(created.task_id, log_msg, created_by)
        if created.task_id:
            serialized = self._serialize_task(self.repo.get_task_by_id(created.task_id))
            user_ids = self._get_task_user_ids(created.task_id)
            ws_manager.send_task_updated(user_ids, serialized)
        return self._serialize_tag(created)

    def update_tag(self, tag_id: str, payload: TaskTagUpdate, user_id: str) -> dict:
        row = self.repo.get_tag_by_id(tag_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        old_tag = row.tag
        row.tag = payload.tag
        self.repo.save_tag(row)
        self.repo.create_log(row.task_id, f"изменил тег с {old_tag} на {row.tag}", user_id)
        return self._serialize_tag(row)

    def delete_tag(self, tag_id: str, user_id: str) -> None:
        row = self.repo.get_tag_by_id(tag_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Tag not found")
        task_id = row.task_id
        actor_fio = self._get_user_fio(user_id)
        log_msg = f"{actor_fio} удалил тэг задачи"
        self.repo.delete_tag(row)
        self.repo.create_log(task_id, log_msg, user_id)
        if task_id:
            serialized = self._serialize_task(self.repo.get_task_by_id(task_id))
            user_ids = self._get_task_user_ids(task_id)
            ws_manager.send_task_updated(user_ids, serialized)

    # --- TaskAccomplishment ---

    @staticmethod
    def _format_elapsed(start: datetime, end: datetime | None) -> str | None:
        if not start or not end:
            return None
        delta = end - start
        total_seconds = int(delta.total_seconds())
        if total_seconds < 0:
            return None
        days, remainder = divmod(total_seconds, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        parts = []
        if days:
            parts.append(f"{days} д.")
        if hours:
            parts.append(f"{hours} ч.")
        if minutes or not parts:
            parts.append(f"{minutes} мин.")
        return " ".join(parts)

    def _serialize_accomplishment(self, row: TaskAccomplishment) -> dict:
        end = row.date_end or row.date_stop
        return {
            "id": row.id,
            "task_id": row.task_id,
            "date_start": row.date_start.strftime("%d.%m.%Y %H:%M:%S") if row.date_start else None,
            "date_end": row.date_end.strftime("%d.%m.%Y %H:%M:%S") if row.date_end else None,
            "date_stop": row.date_stop.strftime("%d.%m.%Y %H:%M:%S") if row.date_stop else None,
            "elapsed": self._format_elapsed(row.date_start, end),
            "status_id": row.status_id,
            "status_name": self.repo.get_status_name(row.status_id),
            "created_by": row.created_by,
        }

    def get_accomplishments(self, task_id: str | None = None) -> list[dict]:
        rows = self.repo.get_accomplishments(task_id)
        return [self._serialize_accomplishment(r) for r in rows]

    def get_accomplishment(self, acc_id: str) -> dict:
        row = self.repo.get_accomplishment_by_id(acc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accomplishment not found")
        return self._serialize_accomplishment(row)

    def create_accomplishment(self, payload: TaskAccomplishmentCreate, created_by: str) -> dict:
        data = payload.model_dump(exclude_none=True)
        data["created_by"] = created_by
        if "status_id" not in data or not data.get("status_id"):
            data["status_id"] = "6b4fbf85-7901-11f1-b481-bc241127d0bd"
        created = self.repo.create_accomplishment(data)
        actor_fio = self._get_user_fio(created_by)
        task_id = created.task_id
        if created.date_end:
            log_msg = f"{actor_fio} завершил выполнение задачи"
        elif created.date_stop:
            log_msg = f"{actor_fio} приостановил выполнение задачи"
        elif created.date_start:
            log_msg = f"{actor_fio} начал выполнение задачи"
        else:
            log_msg = None
        if log_msg and task_id:
            self.repo.create_log(task_id, log_msg, created_by)
            serialized = self._serialize_task(self.repo.get_task_by_id(task_id))
            user_ids = self._get_task_user_ids(task_id)
            ws_manager.send_task_updated(user_ids, serialized)
            for uid in user_ids:
                self._notify_incomplete_count(uid)

        if created.date_end and task_id:
            task = self.repo.get_task_by_id(task_id)
            if task and task.created_by != created_by:
                self._send_vk_task_notification(task.created_by, task, actor_fio, "Выполнение задачи завершено")

        return self._serialize_accomplishment(created)

    def update_accomplishment(self, acc_id: str, payload: TaskAccomplishmentUpdate, user_id: str) -> dict:
        row = self.repo.get_accomplishment_by_id(acc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accomplishment not found")
        updates = payload.model_dump(exclude_unset=True)
        if not updates:
            return self._serialize_accomplishment(row)
        actor_fio = self._get_user_fio(user_id)
        messages = []
        completed_now = False
        if "date_start" in updates and updates["date_start"] and not row.date_start:
            messages.append(f"{actor_fio} начал выполнение задачи")
        if "date_stop" in updates:
            if updates["date_stop"] and not row.date_stop:
                messages.append(f"{actor_fio} приостановил выполнение задачи")
            elif not updates["date_stop"] and row.date_stop:
                messages.append(f"{actor_fio} возобновил выполнение задачи")
        if "date_end" in updates:
            if not updates["date_end"] and row.date_end:
                messages.append(f"{actor_fio} возобновил выполнение задачи")
            elif updates["date_end"] and not row.date_end:
                messages.append(f"{actor_fio} завершил выполнение задачи")
                completed_now = True
        for key, value in updates.items():
            setattr(row, key, value)
        self.repo.save_accomplishment(row)
        task_id = row.task_id
        for msg in messages:
            self.repo.create_log(task_id, msg, user_id)
        if task_id and messages:
            serialized = self._serialize_task(self.repo.get_task_by_id(task_id))
            user_ids = self._get_task_user_ids(task_id)
            ws_manager.send_task_updated(user_ids, serialized)
            for uid in user_ids:
                self._notify_incomplete_count(uid)

        if completed_now and task_id:
            task = self.repo.get_task_by_id(task_id)
            if task and task.created_by != user_id:
                self._send_vk_task_notification(task.created_by, task, actor_fio, "Выполнение задачи завершено")

        return self._serialize_accomplishment(row)

    def delete_accomplishment(self, acc_id: str, user_id: str) -> None:
        row = self.repo.get_accomplishment_by_id(acc_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Accomplishment not found")
        task_id = row.task_id
        self.repo.delete_accomplishment(row)
        self.repo.create_log(task_id, f"удалил выполнение", user_id)
