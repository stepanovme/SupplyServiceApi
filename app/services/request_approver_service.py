from fastapi import HTTPException, status

from app.models.supply_request import RequestApproverCreate, RequestApproverUpdate
from app.repositories.project_user_role_repository import ProjectUserRoleRepository
from app.repositories.request_repository import RequestRepository
from app.services.ws_manager import ws_manager

SUPPLY_MANAGER_ROLE_VALUES = ("Supply manager", "Supply maneger")


class RequestApproverService:
    def __init__(
        self,
        repo: RequestRepository,
        project_user_role_repo: ProjectUserRoleRepository | None = None,
    ) -> None:
        self.repo = repo
        self.project_user_role_repo = project_user_role_repo

    def create(self, request_id: int, data: RequestApproverCreate, user_id: str):
        request_row = self.repo.get_model_by_id(request_id)
        if not request_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        payload = data.model_dump(exclude_unset=True)
        item = self.repo.create_request_log(request_id, payload)

        status_name = item.status_name
        if status_name == "pending":
            ws_manager.send_request_approval_needed(
                item.user_id,
                self._request_payload(request_row, status_name),
            )
            self.repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type="sent_for_approval",
                description=f"Заявка отправлена на согласование пользователю {item.user_id}",
            )

        return self._to_response(item)

    def update(self, request_id: int, log_id: str, data: RequestApproverUpdate, user_id: str):
        request_row = self.repo.get_model_by_id(request_id)
        if not request_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        item = self.repo.get_request_log_by_id(request_id, log_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")

        old_status = item.status_name
        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(item, key, value)

        updated = self.repo.save_request_log(item)
        new_status = updated.status_name

        if new_status == "pending" and new_status != old_status and updated.user_id:
            ws_manager.send_request_approval_needed(
                updated.user_id,
                self._request_payload(request_row, new_status),
            )

        if new_status in ("approved", "rejected") and new_status != old_status:
            participant_ids = self._get_participant_ids(request_row)
            ws_manager.send_request_status_changed(
                participant_ids,
                self._request_payload(request_row, new_status),
                exclude_user_id=user_id,
            )
            event_type = "approved" if new_status == "approved" else "rejected"
            status_label = "согласована" if new_status == "approved" else "отклонена"
            self.repo.create_event_log(
                request_id=request_id,
                user_id=user_id,
                event_type=event_type,
                description=f"Заявка {status_label} пользователем {updated.user_id}",
            )
            if new_status == "approved":
                ws_manager.send_request_invoice_needed(
                    self._get_supply_manager_ids(request_row),
                    self._request_payload(request_row, new_status),
                )

        return self._to_response(updated)

    def delete(self, request_id: int, log_id: str):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        item = self.repo.get_request_log_by_id(request_id, log_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")

        self.repo.delete_request_log(item)
        return None

    def get_my_approvals_summary(self, user_id: str, status_name: str | None = None):
        rows = self.repo.get_request_logs_by_user(user_id, status_name)
        pending_count = self.repo.count_request_logs_by_user_and_status(user_id, "pending")
        return {
            "pending_count": pending_count,
            "items": [self._to_response(item) for item in rows],
        }

    def _get_participant_ids(self, request_row) -> list[str]:
        user_ids: set[str] = set()
        if request_row.created_by:
            user_ids.add(request_row.created_by)
        if request_row.executor:
            user_ids.add(request_row.executor)
        user_ids.update(self.repo.get_request_log_user_ids(request_row.id))
        if self.project_user_role_repo and request_row.object_levels_id:
            for role_row in self.project_user_role_repo.get_by_object_levels_id(request_row.object_levels_id):
                if role_row.user_id:
                    user_ids.add(role_row.user_id)
        return [uid for uid in user_ids if uid]

    def _get_supply_manager_ids(self, request_row) -> list[str]:
        if not self.project_user_role_repo or not request_row.object_levels_id:
            return []
        user_ids: set[str] = set()
        for role_value in SUPPLY_MANAGER_ROLE_VALUES:
            for role_row in self.project_user_role_repo.get_by_object_levels_id(
                request_row.object_levels_id, role_value
            ):
                if role_row.user_id:
                    user_ids.add(role_row.user_id)
        return list(user_ids)

    @staticmethod
    def _request_payload(request_row, status_name: str) -> dict:
        return {
            "id": request_row.id,
            "name": request_row.name,
            "status": status_name,
        }

    @staticmethod
    def _to_response(item):
        return {
            "id": item.id,
            "request_id": item.request_id,
            "user_id": item.user_id,
            "status_name": item.status_name,
            "date_response": item.date_response,
        }