import uuid

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.models.receipt_category import ReceiptCategory, ReceiptCategoryCreate, ReceiptCategoryUpdate, msk_now
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.receipt_category_repository import ReceiptCategoryRepository

# Role that manages the standard (shared) categories - the same role the project already treats as
# "sees everything" (see DepartmentService.get_my).
ADMIN_ROLE_ID = "697afdbf-4f2e-47fb-8277-7127b9b85317"


class ReceiptCategoryService:
    def __init__(self, repo: ReceiptCategoryRepository, auth_user_repo: AuthUserRepository) -> None:
        self.repo = repo
        self.auth_user_repo = auth_user_repo

    def _is_admin(self, user_id: str) -> bool:
        return self.auth_user_repo.has_role(user_id, ADMIN_ROLE_ID)

    def _can_edit(self, category: ReceiptCategory, user_id: str) -> bool:
        if category.owner_user_id is None:
            return self._is_admin(user_id)
        return category.owner_user_id == user_id

    def _serialize(self, category: ReceiptCategory, user_id: str, can_edit: bool | None = None) -> dict:
        return {
            "id": category.id,
            "name": category.name,
            "color": category.color,
            "is_system": category.owner_user_id is None,
            "owner_user_id": category.owner_user_id,
            "can_edit": self._can_edit(category, user_id) if can_edit is None else can_edit,
            "created_at": category.created_at,
            "updated_at": category.updated_at,
        }

    def _get_visible(self, category_id: str, user_id: str) -> ReceiptCategory:
        """Standard or the user's own; anybody else's personal category looks like it doesn't exist."""
        category = self.repo.get_by_id(category_id)
        if not category or (category.owner_user_id is not None and category.owner_user_id != user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Категория чеков не найдена")
        return category

    def _get_editable(self, category_id: str, user_id: str) -> ReceiptCategory:
        category = self._get_visible(category_id, user_id)
        if not self._can_edit(category, user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Стандартные категории может менять только администратор",
            )
        return category

    def _ensure_name_free(self, name: str, owner_user_id: str | None, except_id: str | None = None) -> None:
        existing = self.repo.find_by_name(name, owner_user_id)
        if existing and existing.id != except_id:
            where = "среди стандартных категорий" if owner_user_id is None else "среди ваших категорий"
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Категория «{name}» уже есть {where}")

    # --- API --------------------------------------------------------------------------------
    def get_list(self, user_id: str, scope: str = "all") -> list[dict]:
        is_admin = self._is_admin(user_id)
        return [
            self._serialize(c, user_id, can_edit=is_admin if c.owner_user_id is None else c.owner_user_id == user_id)
            for c in self.repo.get_available(user_id, scope)
        ]

    def get_by_id(self, category_id: str, user_id: str) -> dict:
        return self._serialize(self._get_visible(category_id, user_id), user_id)

    def create(self, payload: ReceiptCategoryCreate, user_id: str) -> dict:
        if payload.is_system and not self._is_admin(user_id):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Стандартные категории может создавать только администратор"
            )
        owner = None if payload.is_system else user_id
        name = payload.name.strip()
        self._ensure_name_free(name, owner)

        category = ReceiptCategory(
            id=str(uuid.uuid4()),
            name=name,
            color=payload.color.upper() if payload.color else None,
            owner_user_id=owner,
            created_by=user_id,
        )
        try:
            self.repo.add(category)
            self.repo.commit()
        except IntegrityError:  # same name created concurrently
            self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"Категория «{name}» уже есть")
        self.repo.refresh(category)
        return self._serialize(category, user_id)

    def update(self, category_id: str, payload: ReceiptCategoryUpdate, user_id: str) -> dict:
        category = self._get_editable(category_id, user_id)
        data = payload.model_dump(exclude_unset=True)

        if data.get("name") is not None:
            name = data["name"].strip()
            self._ensure_name_free(name, category.owner_user_id, except_id=category.id)
            category.name = name
        if "color" in data:
            category.color = data["color"].upper() if data["color"] else None
        category.updated_at = msk_now()
        try:
            self.repo.commit()
        except IntegrityError:
            self.repo.rollback()
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Категория с таким названием уже есть")
        self.repo.refresh(category)
        return self._serialize(category, user_id)

    def delete(self, category_id: str, user_id: str, force: bool = False) -> None:
        """Removing a category also takes it off every receipt that has it, so a category that is
        in use is only deleted with force=true."""
        category = self._get_editable(category_id, user_id)
        receipts = self.repo.count_receipts(category.id)
        if receipts and not force:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Категория привязана к чекам; при удалении она будет снята с них. Повторите с force=true",
                    "usage": {"receipts": receipts},
                },
            )
        self.repo.delete(category)
        self.repo.commit()
