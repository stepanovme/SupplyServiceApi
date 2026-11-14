from app.repositories.task_board_notification_repository import TaskBoardNotificationRepository
from app.models.task import TaskBoardNotificationCreate, TaskBoardNotificationUpdate


class TaskBoardNotificationService:
    def __init__(self, repo: TaskBoardNotificationRepository) -> None:
        self.repo = repo

    def create(self, payload: TaskBoardNotificationCreate) -> dict:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.create(data)
        return self._serialize(row)

    def get_by_id(self, notification_id: int) -> dict | None:
        row = self.repo.get_by_id(notification_id)
        return self._serialize(row) if row else None

    def get_by_user(self, user_id: str) -> list[dict]:
        rows = self.repo.get_by_user(user_id)
        return [self._serialize(r) for r in rows]

    def get_list(
        self,
        task_board_id: str | None = None,
        task_boards_column_id: str | None = None,
        user_id: str | None = None,
    ) -> list[dict]:
        rows = self.repo.get_list(
            task_board_id=task_board_id,
            task_boards_column_id=task_boards_column_id,
            user_id=user_id,
        )
        return [self._serialize(r) for r in rows]

    def update(self, notification_id: int, payload: TaskBoardNotificationUpdate) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(notification_id, data)
        return self._serialize(row) if row else None

    def delete(self, notification_id: int) -> bool:
        return self.repo.delete(notification_id)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "task_board_id": row.task_board_id,
            "task_boards_column_id": row.task_boards_column_id,
            "user_id": row.user_id,
            "expaired_at": row.expaired_at.isoformat() if row.expaired_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
