from app.models.project_user_role import ProjectUserRole, ProjectUserRoleCreate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository


class ProjectUserRoleService:
    def __init__(
        self,
        repo: ProjectUserRoleRepository,
        auth_user_repo: AuthUserRepository | None = None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

    def get_all(self) -> list[ProjectUserRole]:
        return self.repo.get_all()

    def get_all_with_users(self):
        items = self.repo.get_all()
        if not self.auth_user_repo:
            return items

        user_ids = list({item.user_id for item in items if item.user_id})
        users = self.auth_user_repo.get_by_ids(user_ids)
        users_by_id = {user.id: user for user in users}

        return [
            {
                "id": item.id,
                "object_levels_id": item.object_levels_id,
                "user_id": item.user_id,
                "role": item.role.value if hasattr(item.role, "value") else item.role,
                "user": None
                if not users_by_id.get(item.user_id)
                else {
                    "id": users_by_id[item.user_id].id,
                    "name": users_by_id[item.user_id].name,
                    "surname": users_by_id[item.user_id].surname,
                },
            }
            for item in items
        ]

    def create(self, data: ProjectUserRoleCreate) -> ProjectUserRole:
        item_data = data.model_dump(exclude_none=True)
        item = ProjectUserRole(**item_data)
        return self.repo.create(item)

    def delete(self, item_id: str) -> bool:
        item = self.repo.get_by_id(item_id)
        if not item:
            return False
        self.repo.delete(item)
        return True
