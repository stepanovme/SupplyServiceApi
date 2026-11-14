from sqlalchemy.orm import Session

from app.models.object_group import ObjectGroup, ObjectGroupMember


class ObjectGroupRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, group_id: str) -> ObjectGroup | None:
        return self.db.query(ObjectGroup).filter(ObjectGroup.id == group_id).first()

    def get_all(self) -> list[ObjectGroup]:
        return self.db.query(ObjectGroup).order_by(ObjectGroup.name).all()

    def get_by_object_id(self, object_id: str) -> ObjectGroup | None:
        group = self.db.query(ObjectGroup).filter(ObjectGroup.main_object_id == object_id).first()
        if group:
            return group
        return (
            self.db.query(ObjectGroup)
            .join(ObjectGroupMember, ObjectGroupMember.group_id == ObjectGroup.id)
            .filter(ObjectGroupMember.object_id == object_id)
            .first()
        )

    def get_members(self, group_ids: list[str]) -> list[ObjectGroupMember]:
        if not group_ids:
            return []
        return (
            self.db.query(ObjectGroupMember)
            .filter(ObjectGroupMember.group_id.in_(group_ids))
            .order_by(ObjectGroupMember.id)
            .all()
        )

    def find_groups_of_objects(self, object_ids: list[str]) -> dict[str, str]:
        """object_id -> group_id for every given object that already belongs to a group."""
        if not object_ids:
            return {}
        result: dict[str, str] = {}
        for oid, gid in self.db.query(ObjectGroup.main_object_id, ObjectGroup.id).filter(
            ObjectGroup.main_object_id.in_(object_ids)
        ):
            result[oid] = gid
        for oid, gid in self.db.query(ObjectGroupMember.object_id, ObjectGroupMember.group_id).filter(
            ObjectGroupMember.object_id.in_(object_ids)
        ):
            result[oid] = gid
        return result

    def get_member(self, group_id: str, object_id: str) -> ObjectGroupMember | None:
        return (
            self.db.query(ObjectGroupMember)
            .filter(ObjectGroupMember.group_id == group_id, ObjectGroupMember.object_id == object_id)
            .first()
        )

    def add(self, row) -> None:
        self.db.add(row)

    def delete(self, row) -> None:
        self.db.delete(row)

    def commit(self) -> None:
        self.db.commit()

    def rollback(self) -> None:
        self.db.rollback()

    def refresh(self, row) -> None:
        self.db.refresh(row)
