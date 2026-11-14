import json
import os
import re

from fastapi import HTTPException, status

from app.models.supply_request import SupplyRequest, SupplyRequestCreate, SupplyRequestUpdate
from app.models.project_user_role import ProjectUserRoleType
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.department_repository import DepartmentRepository
from app.repositories.object_setting_repository import ObjectSettingRepository
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.request_repository import RequestRepository
from app.services.mistral_retry import mistral_retry, recognize_document_text
from app.repositories.role_repository import (
    DepartmentRoleRepository,
    RolePermissionRepository,
    RoleRepository,
    UserRoleRepository,
)
from app.services.project_name_builder import build_project_name, load_project_reference_maps
from app.services.role_service import RoleService

DEFAULT_NEW_REQUEST_STATUS_ID = "1ff34436-1312-11f1-aa8c-bc241127d0bd"


class RequestService:
    def __init__(
        self,
        repo: RequestRepository,
        auth_user_repo: AuthUserRepository,
        reference_repo: ReferenceObjectRepository,
        project_user_role_repo: ProjectUserRoleRepository | None = None,
        object_setting_repo: ObjectSettingRepository | None = None,
        department_repo: DepartmentRepository | None = None,
        db=None,
    ) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo
        self.reference_repo = reference_repo
        self.project_user_role_repo = project_user_role_repo
        self.object_setting_repo = object_setting_repo
        self.department_repo = department_repo
        self.db = db

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

        counterparty_ids = set()
        for item in requests:
            for invoice in item.get("documents", {}).get("invoices", []):
                if invoice.get("provider_id"):
                    counterparty_ids.add(invoice["provider_id"])
                if invoice.get("payer_id"):
                    counterparty_ids.add(invoice["payer_id"])
        counterparty_names = self.reference_repo.get_counterparty_names(list(counterparty_ids))

        object_level_ids = [item["object_levels_id"] for item in requests if item.get("object_levels_id")]
        (
            levels_by_id,
            objects_by_id,
            contracts_by_id,
            work_types_by_id,
        ) = load_project_reference_maps(self.reference_repo, object_level_ids)

        # Resolve short_name for object_type = "object"
        object_type_ids = {
            item["object_levels_id"]
            for item in requests
            if item.get("object_type") == "object" and item.get("object_levels_id")
        }
        object_short_names: dict[str, str] = {}
        if object_type_ids and self.reference_repo:
            for obj in self.reference_repo.get_objects_by_ids(list(object_type_ids)):
                object_short_names[obj.id] = obj.short_name or obj.full_name

        for item in requests:
            if item.get("object_type") == "object" and item.get("object_levels_id") in object_short_names:
                item["project_name"] = object_short_names[item["object_levels_id"]]
            else:
                item["project_name"] = build_project_name(
                    item.get("object_levels_id"),
                    levels_by_id,
                    objects_by_id,
                    contracts_by_id,
                    work_types_by_id,
                )
            item["required_date_print"] = self._format_print_date(item.get("deadline"))
            item["created_by_user"] = self._map_user(users_by_id.get(item.get("created_by")))
            item["executor_user"] = self._map_user(users_by_id.get(item.get("executor")))

            for log in item.get("logs", []):
                log["user"] = self._map_user(users_by_id.get(log.get("user_id")))

            for invoice in item.get("documents", {}).get("invoices", []):
                invoice["provider_name"] = counterparty_names.get(invoice.get("provider_id"))
                invoice["payer_name"] = counterparty_names.get(invoice.get("payer_id"))

        request_ids = [item["id"] for item in requests if item.get("id")]
        chat_ids_map = self.repo.get_chat_ids_by_request(request_ids)
        for item in requests:
            item["chat_id"] = chat_ids_map.get(item["id"])

        return requests

    def get_available_for_user(self, user_id: str):
        requests = self.get_all()

        visibility = self._get_user_visibility(user_id)

        if visibility == "all":
            return requests

        if visibility == "own_objects" and self.object_setting_repo:
            object_ids = self.object_setting_repo.get_create_request_object_ids_for_user(user_id)
            if object_ids:
                return [
                    item
                    for item in requests
                    if item.get("object_levels_id") in object_ids
                ]

        return [
            item
            for item in requests
            if item.get("created_by") == user_id
            or item.get("executor") == user_id
            or any(log.get("user_id") == user_id for log in item.get("logs", []))
        ]

    def _get_user_visibility(self, user_id: str) -> str | None:
        if not self.db:
            return None
        try:
            dept_ids = self.department_repo.get_department_ids_for_user(user_id) if self.department_repo else []
            role_repo = RoleRepository(self.db)
            perm_repo = RolePermissionRepository(self.db)
            user_role_repo = UserRoleRepository(self.db)
            dept_role_repo = DepartmentRoleRepository(self.db)
            role_service = RoleService(role_repo, perm_repo, user_role_repo, dept_role_repo)
            settings = role_service.get_create_request_effective_settings(user_id, dept_ids)
            if settings:
                return settings.get("visibility")
        except Exception:
            pass
        return None

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

    def create(self, data: SupplyRequestCreate, user_id: str):
        payload = data.model_dump(exclude_none=True)
        object_levels_id = payload.get("object_levels_id")
        if not object_levels_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="object_levels_id is required",
            )

        request_row = SupplyRequest(
            object_levels_id=object_levels_id,
            created_by=user_id,
            status_id=DEFAULT_NEW_REQUEST_STATUS_ID,
            **{k: v for k, v in payload.items() if k != "object_levels_id"},
        )
        created = self.repo.create(request_row)
        return self.get_by_id(created.id)

    def update(self, request_id: int, data: SupplyRequestUpdate):
        request_row = self.repo.get_model_by_id(request_id)
        if not request_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        payload = data.model_dump(exclude_unset=True)
        for field_name, field_value in payload.items():
            setattr(request_row, field_name, field_value)

        updated = self.repo.save(request_row)
        return self.get_by_id(updated.id)

    def delete(self, request_id: int):
        request_row = self.repo.get_model_by_id(request_id)
        if not request_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")
        self.repo.delete(request_row)

    def copy(self, request_id: int, user_id: str):
        source = self.repo.get_model_by_id(request_id)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        source_items = self.repo.get_request_items_by_request(request_id)

        new_request = SupplyRequest(
            object_levels_id=source.object_levels_id,
            object_type=source.object_type,
            name=f"{source.name or ''} (копия)".strip(),
            comment=source.comment,
            created_by=user_id,
            executor=source.executor,
            deadline=source.deadline,
            status_id=DEFAULT_NEW_REQUEST_STATUS_ID,
            copied_from_request_id=source.id,
        )

        created = self.repo.copy_request(request_id, new_request, source_items)
        return self.get_by_id(created.id)

    def split(self, request_id: int, data: dict, user_id: str):
        source = self.repo.get_model_by_id(request_id)
        if not source:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        splits = data.get("splits", [])
        if not splits:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="At least one split is required")

        source_items = self.repo.get_request_items_by_request(request_id)
        items_by_id = {item.id: item for item in source_items}

        all_item_ids = set()
        for split in splits:
            for split_item in split.get("items", []):
                item_id = split_item.get("item_id")
                if item_id not in items_by_id:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Item {item_id} not found in request",
                    )
                if item_id in all_item_ids:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Item {item_id} is used in multiple splits",
                    )
                all_item_ids.add(item_id)

        new_requests_with_items = []
        for i, split in enumerate(splits):
            split_items_data = split.get("items", [])
            quantities = {si["item_id"]: si.get("quantity") for si in split_items_data}
            items_to_move = [items_by_id[si["item_id"]] for si in split_items_data]

            split_name = split.get("name") or f"{source.name or ''} (разделение {i + 1})"

            new_request = SupplyRequest(
                object_levels_id=source.object_levels_id,
                object_type=source.object_type,
                name=split_name.strip(),
                comment=source.comment,
                created_by=user_id,
                executor=source.executor,
                deadline=source.deadline,
                status_id=DEFAULT_NEW_REQUEST_STATUS_ID,
                split_from_request_id=source.id,
            )
            new_requests_with_items.append((new_request, items_to_move, quantities))

        self.repo.split_request(source, new_requests_with_items)
        return self.get_by_id(request_id)

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
    def _format_print_date(value):
        if not value:
            return None
        if hasattr(value, "strftime"):
            return value.strftime("%d.%m.%Y")
        return str(value)

    def _get_supply_manager_level_ids(self, user_id: str) -> set[str]:
        if not self.project_user_role_repo:
            return set()
        # Backward compatibility for possible typo in historical data.
        role_values = [ProjectUserRoleType.SUPPLY_MANAGER.value, "Supply maneger"]
        level_ids: set[str] = set()
        for role in role_values:
            for level_id in self.project_user_role_repo.get_object_level_ids_by_user_and_role(user_id, role):
                if level_id:
                    level_ids.add(level_id)
        return level_ids

    def parse_request_from_file(self, file_bytes: bytes, file_name: str) -> dict:
        from dotenv import load_dotenv

        mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            from pathlib import Path as _Path
            project_root = _Path(__file__).resolve().parents[2]
            load_dotenv(project_root / ".env", override=True)
            mistral_api_key = os.getenv("MISTRAL_API_KEY")
        if not mistral_api_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MISTRAL_API_KEY is not set",
            )

        try:
            from mistralai import Mistral
        except Exception as exc:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="mistralai package is not installed",
            ) from exc

        client = Mistral(api_key=mistral_api_key)

        uploaded_file = mistral_retry(
            client.files.upload,
            file={"file_name": file_name, "content": file_bytes},
            purpose="ocr",
        )
        signed_url = mistral_retry(client.files.get_signed_url, file_id=uploaded_file.id)

        document_text = recognize_document_text(client, signed_url.url)

        prompt = (
            "Извлеки данные заявки (заказа/requests) из документа.\n"
            "Верни ТОЛЬКО валидный JSON объект с ключами:\n"
            "{\n"
            '  "name": string|null,\n'
            '  "comment": string|null,\n'
            '  "items": [\n'
            "    {\n"
            '      "name": string,\n'
            '      "quantity": number,\n'
            '      "unit": string|null,\n'
            '      "comment": string|null\n'
            "    }\n"
            "  ]\n"
            "}\n"
            "Правила:\n"
            "- name — краткое описание заявки (например название товара или \"Заявка на закупку\")\n"
            "- items — список позиций/товаров из документа\n"
            "- quantity — число (без единиц измерения)\n"
            "- unit — единица измерения (шт, кг, м, л и т.д.), если не найдено то null\n"
            "- comment — дополнительные примечания к позиции если есть\n"
            "- Если позиций нет в документе, верни пустой массив items\n"
            "Документ:\n"
            f"{document_text[:15000]}"
        )

        chat_response = mistral_retry(
            client.chat.complete,
            model="ministral-8b-2512",
            messages=[{"role": "user", "content": prompt}],
        )

        raw_content = chat_response.choices[0].message.content
        if isinstance(raw_content, list):
            raw_content = "".join(
                part.get("text", "") if isinstance(part, dict) else str(part)
                for part in raw_content
            )

        parsed = self._extract_json_payload(raw_content)

        items = parsed.get("items", [])
        if isinstance(items, list):
            cleaned_items = []
            for item in items:
                if not isinstance(item, dict):
                    continue
                cleaned_items.append({
                    "name": str(item.get("name", "")) if item.get("name") else None,
                    "quantity": float(item["quantity"]) if item.get("quantity") is not None else 0,
                    "unit": str(item["unit"]) if item.get("unit") else None,
                    "comment": str(item["comment"]) if item.get("comment") else None,
                })
            items = cleaned_items

        return {
            "name": str(parsed.get("name", "")) if parsed.get("name") else None,
            "comment": str(parsed.get("comment", "")) if parsed.get("comment") else None,
            "items": items,
        }

    @staticmethod
    def _extract_json_payload(content: str) -> dict:
        if not content:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Mistral returned empty response",
            )
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned)
            cleaned = re.sub(r"\s*```$", "", cleaned)
        try:
            return json.loads(cleaned)
        except Exception:
            match = re.search(r"\{.*\}", cleaned, flags=re.S)
            if not match:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot parse JSON from Mistral response",
                )
            try:
                return json.loads(match.group(0))
            except Exception as exc:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid JSON in Mistral response: {exc}",
                ) from exc
