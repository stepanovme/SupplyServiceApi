from fastapi import HTTPException, status

from app.models.supply_request import StatusRef
from app.models.ticket import (
    Ticket,
    TicketCreate,
    TicketUpdate,
    TicketUser,
    TicketUserCreate,
    TicketUserUpdate,
)
from app.repositories.ticket_repository import TicketRepository
from app.repositories.auth_user_repository import AuthUserRepository


class TicketService:
    def __init__(self, repo: TicketRepository, auth_user_repo: AuthUserRepository | None = None) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

    # --- Ticket ---

    def get_all(self) -> list[dict]:
        rows = self.repo.get_all()
        status_map = self._get_status_map(rows)
        return [self._serialize(r, status_map) for r in rows]

    def get_my(self, user_id: str) -> list[dict]:
        rows = self.repo.get_by_user(user_id)
        status_map = self._get_status_map(rows)
        return [self._serialize(r, status_map) for r in rows]

    def get_by_id(self, ticket_id: int) -> dict:
        row = self.repo.get_by_id(ticket_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        status_map = self._get_status_map([row])
        return self._serialize(row, status_map)

    def create(self, payload: TicketCreate, created_by: str) -> dict:
        data = payload.model_dump(exclude_none=True)
        if not data.get("chat_id"):
            data.pop("chat_id", None)
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def update(self, ticket_id: int, payload: TicketUpdate) -> dict:
        row = self.repo.get_by_id(ticket_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        updates = payload.model_dump(exclude_unset=True)
        if "chat_id" in updates and not updates["chat_id"]:
            updates["chat_id"] = None
        if not updates:
            return self._serialize(row)
        for key, value in updates.items():
            setattr(row, key, value)
        updated = self.repo.save(row)
        return self._serialize(updated)

    def delete(self, ticket_id: int) -> None:
        row = self.repo.get_by_id(ticket_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket not found")
        self.repo.delete(row)

    # --- TicketUser ---

    def get_users_by_ticket(self, ticket_id: int) -> list[dict]:
        rows = self.repo.get_users_by_ticket(ticket_id)
        return [self._serialize_user(r) for r in rows]

    def create_user(self, payload: TicketUserCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create_user(data)
        return self._serialize_user(row)

    def update_user(self, user_rel_id: int, payload: TicketUserUpdate) -> dict:
        row = self.repo.get_user_by_id(user_rel_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket user not found")
        updates = payload.model_dump(exclude_unset=True)
        for key, value in updates.items():
            setattr(row, key, value)
        updated = self.repo.save_user(row)
        return self._serialize_user(updated)

    def delete_user(self, user_rel_id: int) -> None:
        row = self.repo.get_user_by_id(user_rel_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Ticket user not found")
        self.repo.delete_user(row)

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

    def _serialize(self, row: Ticket, status_map: dict[str, str] | None = None) -> dict:
        user_ids = {row.created_by}
        user_roles = self.repo.get_users_by_ticket(row.id)
        for ur in user_roles:
            user_ids.add(ur.user_id)
            user_ids.add(ur.created_by)
        users_by_id = self._get_users_map(list(user_ids))
        type_label = {"suggestion": "Предложение", "question": "Вопрос", "problem": "Проблема"}
        status_name = (status_map or {}).get(row.status_id)
        return {
            "id": row.id,
            "type": row.type,
            "type_label": type_label.get(row.type, row.type),
            "status_id": row.status_id,
            "status_name": status_name,
            "chat_id": row.chat_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
            "users": [self._serialize_user(ur) for ur in user_roles],
        }

    def _get_status_map(self, rows: list[Ticket]) -> dict[str, str]:
        status_ids = list({r.status_id for r in rows if r.status_id})
        if not status_ids:
            return {}
        statuses = self.repo.db.query(StatusRef).filter(StatusRef.id.in_(status_ids)).all()
        return {s.id: s.name for s in statuses}

    def _serialize_user(self, row: TicketUser) -> dict:
        users_by_id = self._get_users_map([row.user_id, row.created_by])
        return {
            "id": row.id,
            "ticket_id": row.ticket_id,
            "user_id": row.user_id,
            "user": self._map_user(users_by_id.get(row.user_id)),
            "role_id": row.role_id,
            "created_at": row.created_at,
            "created_by": row.created_by,
            "created_by_user": self._map_user(users_by_id.get(row.created_by)),
        }
