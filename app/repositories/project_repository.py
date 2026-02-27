from sqlalchemy.orm import Session

from app.models.project import Project


class ProjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_all(self) -> list[Project]:
        return self.db.query(Project).all()

    def create(self, project: Project) -> Project:
        self.db.add(project)
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_by_id(self, project_id: str) -> Project | None:
        return self.db.query(Project).filter(Project.id == project_id).first()

    def save(self, project: Project) -> Project:
        self.db.commit()
        self.db.refresh(project)
        return project

    def get_active_object_ids(self, object_ids: list[str]) -> set[str]:
        unique_ids = list({object_id for object_id in object_ids if object_id})
        if not unique_ids:
            return set()

        rows = (
            self.db.query(Project.object_id)
            .filter(
                Project.object_id.in_(unique_ids),
                Project.is_active.is_(True),
            )
            .all()
        )
        return {row[0] for row in rows}
