import uuid

from sqlalchemy.orm import Session

from app.models.department import Department, DepartmentUser


class DepartmentRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Department ---

    def get_all(self) -> list[Department]:
        return self.db.query(Department).order_by(Department.created_at.desc()).all()

    def get_by_user(self, user_id: str) -> list[Department]:
        from sqlalchemy import union
        created_q = self.db.query(Department.id).filter(Department.created_by == user_id)
        member_q = self.db.query(DepartmentUser.departament_id).filter(
            DepartmentUser.user_id == user_id
        )
        union_q = union(created_q, member_q).subquery()
        return (
            self.db.query(Department)
            .filter(Department.id.in_(union_q))
            .order_by(Department.created_at.desc())
            .all()
        )

    def get_by_id(self, dept_id: int) -> Department | None:
        return self.db.query(Department).filter(Department.id == dept_id).first()

    def create(self, payload: dict) -> Department:
        row = Department(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Department) -> Department:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Department) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- DepartmentUser ---

    def get_users_by_department(self, departament_id: int) -> list[DepartmentUser]:
        return self.db.query(DepartmentUser).filter(
            DepartmentUser.departament_id == departament_id
        ).order_by(DepartmentUser.created_at.desc()).all()

    def get_user_by_id(self, user_id: str) -> DepartmentUser | None:
        return self.db.query(DepartmentUser).filter(DepartmentUser.id == user_id).first()

    def create_user(self, payload: dict) -> DepartmentUser:
        row = DepartmentUser(id=str(uuid.uuid4()), **payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_user(self, row: DepartmentUser) -> DepartmentUser:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user(self, row: DepartmentUser) -> None:
        self.db.delete(row)
        self.db.commit()
