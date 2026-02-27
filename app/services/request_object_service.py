from app.repositories.project_repository import ProjectRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.project_name_builder import build_project_name, load_project_reference_maps


class RequestObjectService:
    def __init__(
        self,
        reference_repo: ReferenceObjectRepository,
        project_user_role_repo: ProjectUserRoleRepository,
        project_repo: ProjectRepository,
    ) -> None:
        self.reference_repo = reference_repo
        self.project_user_role_repo = project_user_role_repo
        self.project_repo = project_repo

    def get_all(self):
        level_ids = self.reference_repo.get_level_ids_by_type("worktype")
        return self._build_response(level_ids)

    def get_available_for_user(self, user_id: str):
        level_ids = self.project_user_role_repo.get_object_level_ids_by_user_and_role(
            user_id,
            "Requester",
        )
        return self._build_response(level_ids)

    def _build_response(self, level_ids: list[str]):
        ordered_unique_ids = list(dict.fromkeys([level_id for level_id in level_ids if level_id]))
        if not ordered_unique_ids:
            return []

        (
            levels_by_id,
            objects_by_id,
            contracts_by_id,
            work_types_by_id,
        ) = load_project_reference_maps(self.reference_repo, ordered_unique_ids)
        active_object_ids = self.project_repo.get_active_object_ids(
            [level.object_id for level in levels_by_id.values() if level.object_id]
        )

        result = []
        for level_id in ordered_unique_ids:
            level = levels_by_id.get(level_id)
            if not level:
                continue
            if level.object_id not in active_object_ids:
                continue

            name = build_project_name(
                level_id,
                levels_by_id,
                objects_by_id,
                contracts_by_id,
                work_types_by_id,
            )
            result.append({"id": level_id, "name": name})
        return result
