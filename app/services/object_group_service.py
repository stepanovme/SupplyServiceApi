import uuid

from fastapi import HTTPException, status

from app.models.object_group import (
    ObjectGroup,
    ObjectGroupAddObjects,
    ObjectGroupCreate,
    ObjectGroupMember,
    ObjectGroupUpdate,
    msk_now,
)
from app.repositories.object_group_repository import ObjectGroupRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository


class ObjectGroupService:
    """A group = one main object plus any number of other objects attached to it.
    An object can be in only one group (as main or as a member)."""

    def __init__(self, repo: ObjectGroupRepository, reference_repo: ReferenceObjectRepository) -> None:
        self.repo = repo
        self.reference_repo = reference_repo

    # --- helpers -------------------------------------------------------------------------
    def _get_or_404(self, group_id: str) -> ObjectGroup:
        group = self.repo.get_by_id(group_id)
        if not group:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Группа объектов не найдена")
        return group

    def _ensure_objects_exist(self, object_ids: list[str]) -> None:
        unique = list(dict.fromkeys(object_ids))
        found = {row.id for row in self.reference_repo.get_objects_by_ids(unique)}
        missing = [oid for oid in unique if oid not in found]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Объекты не найдены: {', '.join(missing)}",
            )

    def _ensure_objects_free(self, object_ids: list[str], allowed_group_id: str | None = None) -> None:
        taken = self.repo.find_groups_of_objects(object_ids)
        busy = [oid for oid, gid in taken.items() if gid != allowed_group_id]
        if busy:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Объекты уже состоят в другой группе: {', '.join(busy)}",
            )

    def _serialize_many(self, groups: list[ObjectGroup]) -> list[dict]:
        members = self.repo.get_members([g.id for g in groups])
        by_group: dict[str, list[str]] = {}
        for m in members:
            by_group.setdefault(m.group_id, []).append(m.object_id)

        all_ids = [g.main_object_id for g in groups] + [oid for ids in by_group.values() for oid in ids]
        objects = {row.id: row for row in self.reference_repo.get_objects_by_ids(all_ids)}

        def obj(oid: str) -> dict:
            row = objects.get(oid)
            return {
                "id": oid,
                "short_name": row.short_name if row else None,
                "full_name": row.full_name if row else None,
                "address": row.address if row else None,
            }

        return [
            {
                "id": g.id,
                "name": g.name,
                "comment": g.comment,
                "main_object": obj(g.main_object_id),
                "objects": [obj(oid) for oid in by_group.get(g.id, [])],
                "objects_count": 1 + len(by_group.get(g.id, [])),
                "created_by": g.created_by,
                "created_at": g.created_at,
                "updated_at": g.updated_at,
            }
            for g in groups
        ]

    def _serialize(self, group: ObjectGroup) -> dict:
        return self._serialize_many([group])[0]

    # --- queries -------------------------------------------------------------------------
    def get_list(self) -> list[dict]:
        return self._serialize_many(self.repo.get_all())

    def get_by_id(self, group_id: str) -> dict:
        return self._serialize(self._get_or_404(group_id))

    def get_by_object(self, object_id: str) -> dict | None:
        group = self.repo.get_by_object_id(object_id)
        return self._serialize(group) if group else None

    # --- commands ------------------------------------------------------------------------
    def create(self, payload: ObjectGroupCreate, user_id: str) -> dict:
        member_ids = [oid for oid in dict.fromkeys(payload.object_ids) if oid != payload.main_object_id]
        all_ids = [payload.main_object_id, *member_ids]
        self._ensure_objects_exist(all_ids)
        self._ensure_objects_free(all_ids)

        group = ObjectGroup(
            id=str(uuid.uuid4()),
            name=payload.name.strip(),
            main_object_id=payload.main_object_id,
            comment=payload.comment,
            created_by=user_id,
        )
        try:
            self.repo.add(group)
            self.repo.commit()  # the group row must exist before members reference it
            for oid in member_ids:
                self.repo.add(ObjectGroupMember(group_id=group.id, object_id=oid, created_by=user_id))
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        return self._serialize(group)

    def update(self, group_id: str, payload: ObjectGroupUpdate) -> dict:
        group = self._get_or_404(group_id)
        data = payload.model_dump(exclude_unset=True)

        if data.get("name") is not None:
            group.name = data["name"].strip()
        if "comment" in data:
            group.comment = data["comment"]

        new_main = data.get("main_object_id")
        if new_main and new_main != group.main_object_id:
            self._ensure_objects_exist([new_main])
            self._ensure_objects_free([new_main], allowed_group_id=group_id)
            old_main = group.main_object_id
            promoted = self.repo.get_member(group_id, new_main)
            if promoted:  # a member becomes main; the old main takes its place among members
                self.repo.delete(promoted)
                self.repo.commit()
            group.main_object_id = new_main
            self.repo.add(ObjectGroupMember(group_id=group_id, object_id=old_main, created_by=group.created_by))

        group.updated_at = msk_now()
        try:
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        return self._serialize(group)

    def delete(self, group_id: str) -> None:
        group = self._get_or_404(group_id)
        self.repo.delete(group)  # members go away via ON DELETE CASCADE
        self.repo.commit()

    def add_objects(self, group_id: str, payload: ObjectGroupAddObjects, user_id: str) -> dict:
        group = self._get_or_404(group_id)
        ids = [oid for oid in dict.fromkeys(payload.object_ids) if oid != group.main_object_id]
        self._ensure_objects_exist(ids)
        self._ensure_objects_free(ids, allowed_group_id=group_id)
        try:
            for oid in ids:
                if not self.repo.get_member(group_id, oid):
                    self.repo.add(ObjectGroupMember(group_id=group_id, object_id=oid, created_by=user_id))
            group.updated_at = msk_now()
            self.repo.commit()
        except Exception:
            self.repo.rollback()
            raise
        return self._serialize(group)

    def remove_object(self, group_id: str, object_id: str) -> dict:
        group = self._get_or_404(group_id)
        if object_id == group.main_object_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Главный объект нельзя убрать из группы: назначьте другой главный объект или удалите группу",
            )
        member = self.repo.get_member(group_id, object_id)
        if not member:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Объект не входит в эту группу")
        self.repo.delete(member)
        group.updated_at = msk_now()
        self.repo.commit()
        return self._serialize(group)
