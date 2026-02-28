from fastapi import HTTPException, status

from app.models.supply_request import RequestApproverCreate, RequestApproverUpdate
from app.repositories.request_repository import RequestRepository


class RequestApproverService:
    def __init__(self, repo: RequestRepository) -> None:
        self.repo = repo

    def create(self, request_id: int, data: RequestApproverCreate):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        payload = data.model_dump(exclude_unset=True)
        item = self.repo.create_request_log(request_id, payload)
        return self._to_response(item)

    def update(self, request_id: int, log_id: str, data: RequestApproverUpdate):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        item = self.repo.get_request_log_by_id(request_id, log_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")

        payload = data.model_dump(exclude_unset=True)
        for key, value in payload.items():
            setattr(item, key, value)

        updated = self.repo.save_request_log(item)
        return self._to_response(updated)

    def delete(self, request_id: int, log_id: str):
        if not self.repo.request_exists(request_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Request not found")

        item = self.repo.get_request_log_by_id(request_id, log_id)
        if not item:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Approver not found")

        self.repo.delete_request_log(item)
        return None

    @staticmethod
    def _to_response(item):
        return {
            "id": item.id,
            "request_id": item.request_id,
            "user_id": item.user_id,
            "status_name": item.status_name,
            "date_response": item.date_response,
        }
