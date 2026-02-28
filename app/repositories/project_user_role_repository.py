from sqlalchemy.orm import Session

from app.models.project_user_role import ProjectUserRole


class ProjectUserRoleRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[ProjectUserRole]:
        return self.db.query(ProjectUserRole).all()

    def get_by_object_levels_id(
        self,
        object_levels_id: str,
        role: str | None = None,
    ) -> list[ProjectUserRole]:
        query = self.db.query(ProjectUserRole).filter(
            ProjectUserRole.object_levels_id == object_levels_id
        )
        if role:
            query = query.filter(ProjectUserRole.role == role)
        return query.all()

    def create(self, item: ProjectUserRole) -> ProjectUserRole:
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return item

    def get_by_id(self, item_id: str) -> ProjectUserRole | None:
        return self.db.query(ProjectUserRole).filter(ProjectUserRole.id == item_id).first()

    def delete(self, item: ProjectUserRole) -> None:
        self.db.delete(item)
        self.db.commit()

    def get_object_level_ids_by_user_and_role(self, user_id: str, role: str) -> list[str]:
        rows = (
            self.db.query(ProjectUserRole.object_levels_id)
            .filter(
                ProjectUserRole.user_id == user_id,
                ProjectUserRole.role == role,
            )
            .all()
        )
        return [row[0] for row in rows]
