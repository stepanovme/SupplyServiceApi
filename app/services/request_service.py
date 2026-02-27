from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_repository import RequestRepository
from app.services.project_name_builder import build_project_name, load_project_reference_maps


class RequestService:
    def __init__(
        self,
        repo: RequestRepository,
        auth_user_repo: AuthUserRepository,
        reference_repo: ReferenceObjectRepository,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo

    def get_all(self):
        requests = self.repo.get_all()
        if not requests:
            return []

        user_ids = set()
        for item in requests:
            if item.get("created_by"):
                user_ids.add(item["created_by"])
            if item.get("executor"):
                user_ids.add(item["executor"])
            for log in item.get("logs", []):
                if log.get("user_id"):
                    user_ids.add(log["user_id"])

        users = self.auth_user_repo.get_by_ids(list(user_ids))
        users_by_id = {user.id: user for user in users}

        object_level_ids = [item["object_levels_id"] for item in requests if item.get("object_levels_id")]
        (
            levels_by_id,
            objects_by_id,
            contracts_by_id,
            work_types_by_id,
        ) = load_project_reference_maps(self.reference_repo, object_level_ids)

        for item in requests:
            item["project_name"] = build_project_name(
                item.get("object_levels_id"),
                levels_by_id,
                objects_by_id,
                contracts_by_id,
                work_types_by_id,
            )
            item["created_by_user"] = self._map_user(users_by_id.get(item.get("created_by")))
            item["executor_user"] = self._map_user(users_by_id.get(item.get("executor")))

            for log in item.get("logs", []):
                log["user"] = self._map_user(users_by_id.get(log.get("user_id")))

        return requests

    def get_available_for_user(self, user_id: str):
        requests = self.get_all()
        return [
            item
            for item in requests
            if item.get("created_by") == user_id
            or item.get("executor") == user_id
            or any(log.get("user_id") == user_id for log in item.get("logs", []))
        ]

    def get_by_id(self, request_id: int):
        requests = self.get_all()
        for item in requests:
            if item.get("id") == request_id:
                return item
        return None

    def get_available_for_user_by_id(self, user_id: str, request_id: int):
        requests = self.get_available_for_user(user_id)
        for item in requests:
            if item.get("id") == request_id:
                return item
        return None

    @staticmethod
    def _map_user(user):
        if not user:
            return None
        name_initial = f"{user.name[0]}." if user.name else ""
        patronymic_initial = f"{user.patronymic[0]}." if user.patronymic else ""
        short_fio = " ".join(
            part for part in [user.surname, name_initial, patronymic_initial] if part
        ).strip()
        return {
            "id": user.id,
            "name": user.name,
            "surname": user.surname,
            "patronymic": user.patronymic,
            "short_fio": short_fio,
        }
