from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_repository import RequestRepository


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
        levels_by_id = self.reference_repo.get_levels_tree(object_level_ids)
        object_ids = [level.object_id for level in levels_by_id.values() if level.object_id]
        objects = self.reference_repo.get_objects_by_ids(object_ids)
        objects_by_id = {obj.id: obj for obj in objects}
        contract_ids = [level.contract_id for level in levels_by_id.values() if level.contract_id]
        contracts = self.reference_repo.get_contracts_by_ids(contract_ids)
        contracts_by_id = {contract.id: contract for contract in contracts}
        work_type_ids = [level.work_type for level in levels_by_id.values() if level.work_type]
        work_types = self.reference_repo.get_work_types_by_ids(work_type_ids)
        work_types_by_id = {work_type.id: work_type for work_type in work_types}

        for item in requests:
            item["project_name"] = self._build_project_name(
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

    @staticmethod
    def _build_project_name(
        object_level_id,
        levels_by_id,
        objects_by_id,
        contracts_by_id,
        work_types_by_id,
    ):
        if not object_level_id:
            return None

        level = levels_by_id.get(object_level_id)
        if not level:
            return None

        parts_by_type = {"section": None, "agreement": None, "worktype": None}
        current = level
        while current:
            if current.level_type == "section":
                parts_by_type["section"] = current.name or parts_by_type["section"]
            elif current.level_type == "agreement":
                contract_name = None
                if current.contract_id and contracts_by_id.get(current.contract_id):
                    contract_name = contracts_by_id[current.contract_id].name
                parts_by_type["agreement"] = contract_name or current.name or parts_by_type["agreement"]
            elif current.level_type == "worktype":
                work_type_name = None
                if current.work_type and work_types_by_id.get(current.work_type):
                    work_type_name = work_types_by_id[current.work_type].name
                parts_by_type["worktype"] = work_type_name or current.name or parts_by_type["worktype"]
            if not current.parent_id:
                break
            current = levels_by_id.get(current.parent_id)

        obj = objects_by_id.get(level.object_id)
        object_name = None
        if obj:
            object_name = obj.short_name or obj.full_name

        name_parts = [object_name, parts_by_type["section"], parts_by_type["agreement"], parts_by_type["worktype"]]
        filtered = [part for part in name_parts if part]
        return " - ".join(filtered) if filtered else None
