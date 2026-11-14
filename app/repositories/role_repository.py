import uuid

from sqlalchemy.orm import Session

from app.models.role import Role, RolePermission, UserRole, DepartmentRole


class RoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self, active_only: bool = True) -> list[Role]:
        query = self.db.query(Role)
        if active_only:
            query = query.filter(Role.is_active == True)
        return query.order_by(Role.created_at.desc()).all()

    def get_by_id(self, role_id: str) -> Role | None:
        return self.db.query(Role).filter(Role.id == role_id).first()

    def get_by_name(self, name: str) -> Role | None:
        return self.db.query(Role).filter(Role.name == name).first()

    def create(self, data: dict) -> Role:
        row = Role(id=str(uuid.uuid4()), **data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Role) -> Role:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Role) -> None:
        self.db.delete(row)
        self.db.commit()


class RolePermissionRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_role(self, role_id: str) -> list[RolePermission]:
        return self.db.query(RolePermission).filter(RolePermission.role_id == role_id).order_by(RolePermission.created_at.desc()).all()

    def get_by_role_and_key(self, role_id: str, permission_key: str) -> RolePermission | None:
        return self.db.query(RolePermission).filter(
            RolePermission.role_id == role_id,
            RolePermission.permission_key == permission_key,
        ).first()

    def get_settings_for_role(self, role_id: str) -> dict:
        rows = self.get_by_role(role_id)
        return {r.permission_key: r.settings for r in rows}

    def create(self, data: dict) -> RolePermission:
        row = RolePermission(id=str(uuid.uuid4()), **data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: RolePermission) -> RolePermission:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: RolePermission) -> None:
        self.db.delete(row)
        self.db.commit()

    def delete_by_role(self, role_id: str) -> None:
        self.db.query(RolePermission).filter(RolePermission.role_id == role_id).delete(synchronize_session="fetch")
        self.db.commit()


class UserRoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_user(self, user_id: str) -> list[UserRole]:
        return self.db.query(UserRole).filter(UserRole.user_id == user_id).order_by(UserRole.created_at.desc()).all()

    def get_by_role(self, role_id: str) -> list[UserRole]:
        return self.db.query(UserRole).filter(UserRole.role_id == role_id).all()

    def get_roles_for_user(self, user_id: str) -> list[Role]:
        rows = self.get_by_user(user_id)
        role_ids = [ur.role_id for ur in rows]
        if not role_ids:
            return []
        return self.db.query(Role).filter(Role.id.in_(role_ids)).all()

    def get_users_for_role(self, role_id: str) -> list[UserRole]:
        return self.db.query(UserRole).filter(UserRole.role_id == role_id).all()

    def create(self, data: dict) -> UserRole:
        row = UserRole(id=str(uuid.uuid4()), **data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_by_user_and_role(self, user_id: str, role_id: str) -> None:
        self.db.query(UserRole).filter(
            UserRole.user_id == user_id,
            UserRole.role_id == role_id,
        ).delete(synchronize_session="fetch")
        self.db.commit()

    def delete_by_role(self, role_id: str) -> None:
        self.db.query(UserRole).filter(UserRole.role_id == role_id).delete(synchronize_session="fetch")
        self.db.commit()


class DepartmentRoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_department(self, department_id: int) -> list[DepartmentRole]:
        return self.db.query(DepartmentRole).filter(DepartmentRole.department_id == department_id).order_by(DepartmentRole.created_at.desc()).all()

    def get_by_role(self, role_id: str) -> list[DepartmentRole]:
        return self.db.query(DepartmentRole).filter(DepartmentRole.role_id == role_id).all()

    def get_roles_for_department(self, department_id: int) -> list[Role]:
        rows = self.get_by_department(department_id)
        role_ids = [dr.role_id for dr in rows]
        if not role_ids:
            return []
        return self.db.query(Role).filter(Role.id.in_(role_ids)).all()

    def get_departments_for_role(self, role_id: str) -> list[DepartmentRole]:
        return self.db.query(DepartmentRole).filter(DepartmentRole.role_id == role_id).all()

    def create(self, data: dict) -> DepartmentRole:
        row = DepartmentRole(id=str(uuid.uuid4()), **data)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_by_department_and_role(self, department_id: int, role_id: str) -> None:
        self.db.query(DepartmentRole).filter(
            DepartmentRole.department_id == department_id,
            DepartmentRole.role_id == role_id,
        ).delete(synchronize_session="fetch")
        self.db.commit()

    def delete_by_role(self, role_id: str) -> None:
        self.db.query(DepartmentRole).filter(DepartmentRole.role_id == role_id).delete(synchronize_session="fetch")
        self.db.commit()