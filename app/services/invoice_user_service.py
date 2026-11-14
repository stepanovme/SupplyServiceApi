from fastapi import HTTPException, status

from app.models.invoice_user import InvoiceUser, InvoiceUserCreate, InvoiceUserUpdate
from app.repositories.invoice_user_repository import InvoiceUserRepository


class InvoiceUserService:
    def __init__(self, repo: InvoiceUserRepository) -> None:
        self.repo = repo

    def get_all(self) -> list[InvoiceUser]:
        return self.repo.get_all()

    def get_by_id(self, item_id: int) -> InvoiceUser:
        item = self.repo.get_by_id(item_id)
        if not item:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Invoice user not found",
            )
        return item

    def create(self, data: InvoiceUserCreate, created_by: str) -> InvoiceUser:
        item = InvoiceUser(**data.model_dump(), created_by=created_by)
        return self.repo.create(item)

    def update(self, item_id: int, data: InvoiceUserUpdate) -> InvoiceUser:
        item = self.get_by_id(item_id)
        update_data = data.model_dump(exclude_none=True)
        for key, value in update_data.items():
            setattr(item, key, value)
        return self.repo.save(item)

    def delete(self, item_id: int) -> None:
        item = self.get_by_id(item_id)
        self.repo.delete(item)
