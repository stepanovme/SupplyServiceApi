from sqlalchemy.orm import Session

from app.models.department import DepartmentUser
from app.models.object_setting import ObjectSetting


class ObjectSettingRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[ObjectSetting]:
        return self.db.query(ObjectSetting).all()

    def get_by_id(self, item_id: str) -> ObjectSetting | None:
        return self.db.query(ObjectSetting).filter(ObjectSetting.id == item_id).first()

    def get_by_object_id(self, object_id: str) -> list[ObjectSetting]:
        return self.db.query(ObjectSetting).filter(ObjectSetting.object_id == object_id).all()

    def get_create_request_object_ids_for_user(self, user_id: str) -> set[str]:
        direct = (
            self.db.query(ObjectSetting.object_id)
            .filter(ObjectSetting.user_id == user_id, ObjectSetting.role == 'create_request')
            .all()
        )
        result = {row[0] for row in direct}

        user_dept_ids = (
            self.db.query(DepartmentUser.departament_id)
            .filter(DepartmentUser.user_id == user_id)
            .all()
        )
        dept_ids = [row[0] for row in user_dept_ids]
        if dept_ids:
            dept_based = (
                self.db.query(ObjectSetting.object_id)
                .filter(ObjectSetting.department_id.in_(dept_ids), ObjectSetting.role == 'create_request')
                .all()
            )
            for row in dept_based:
                result.add(row[0])

        return result

    def get_all_object_ids_for_user(self, user_id: str) -> set[str]:
        direct = (
            self.db.query(ObjectSetting.object_id)
            .filter(ObjectSetting.user_id == user_id)
            .all()
        )
        result = {row[0] for row in direct}

        user_dept_ids = (
            self.db.query(DepartmentUser.departament_id)
            .filter(DepartmentUser.user_id == user_id)
            .all()
        )
        dept_ids = [row[0] for row in user_dept_ids]
        if dept_ids:
            dept_based = (
                self.db.query(ObjectSetting.object_id)
                .filter(ObjectSetting.department_id.in_(dept_ids))
                .all()
            )
            for row in dept_based:
                result.add(row[0])

        return result

    def get_accessible_object_ids_for_user(self, user_id: str) -> set[str]:
        direct = (
            self.db.query(ObjectSetting.object_id)
            .filter(ObjectSetting.user_id == user_id, ObjectSetting.role == 'view_invoice')
            .all()
        )
        result = {row[0] for row in direct}

        user_dept_ids = (
            self.db.query(DepartmentUser.departament_id)
            .filter(DepartmentUser.user_id == user_id)
            .all()
        )
        dept_ids = [row[0] for row in user_dept_ids]
        if dept_ids:
            dept_based = (
                self.db.query(ObjectSetting.object_id)
                .filter(ObjectSetting.department_id.in_(dept_ids), ObjectSetting.role == 'view_invoice')
                .all()
            )
            for row in dept_based:
                result.add(row[0])

        return result

    def get_approve_request_users(self, object_id: str) -> list[dict]:
        settings = (
            self.db.query(ObjectSetting.user_id, ObjectSetting.department_id)
            .filter(ObjectSetting.role == 'approve_request', ObjectSetting.object_id == object_id)
            .all()
        )

        result = []
        for user_id, dept_id in settings:
            if user_id:
                result.append({"user_id": user_id, "object_id": object_id})
            elif dept_id:
                dept_users = (
                    self.db.query(DepartmentUser.user_id)
                    .filter(DepartmentUser.departament_id == dept_id)
                    .all()
                )
                for row in dept_users:
                    result.append({"user_id": row[0], "object_id": object_id})

        return result

    def create(self, item: ObjectSetting) -> ObjectSetting:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def save(self, item: ObjectSetting) -> ObjectSetting:
        self.db.commit()
        self.db.refresh(item)
        return item

    def delete(self, item: ObjectSetting) -> None:
        self.db.delete(item)
        self.db.commit()
