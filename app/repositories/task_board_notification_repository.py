from datetime import datetime

from sqlalchemy.orm import Session

from app.database import msk_now
from app.models.task import TaskBoardNotification


class TaskBoardNotificationRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> TaskBoardNotification:
        row = TaskBoardNotification(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, notification_id: int) -> TaskBoardNotification | None:
        return self.db.query(TaskBoardNotification).filter(TaskBoardNotification.id == notification_id).first()

    def get_by_user(self, user_id: str) -> list[TaskBoardNotification]:
        return (
            self.db.query(TaskBoardNotification)
            .filter(TaskBoardNotification.user_id == user_id)
            .order_by(TaskBoardNotification.created_at.desc())
            .all()
        )

    def get_list(
        self,
        task_board_id: str | None = None,
        task_boards_column_id: str | None = None,
        user_id: str | None = None,
    ) -> list[TaskBoardNotification]:
        q = self.db.query(TaskBoardNotification)
        if task_board_id:
            q = q.filter(TaskBoardNotification.task_board_id == task_board_id)
        if task_boards_column_id:
            q = q.filter(TaskBoardNotification.task_boards_column_id == task_boards_column_id)
        if user_id:
            q = q.filter(TaskBoardNotification.user_id == user_id)
        return q.order_by(TaskBoardNotification.created_at.desc()).all()

    def is_muted(self, user_id: str, task_board_id: str | None = None, task_boards_column_id: str | None = None) -> bool:
        if not task_board_id and not task_boards_column_id:
            return False
        q = self.db.query(TaskBoardNotification).filter(TaskBoardNotification.user_id == user_id)
        if task_board_id:
            q = q.filter(TaskBoardNotification.task_board_id == task_board_id)
        if task_boards_column_id:
            q = q.filter(
                (TaskBoardNotification.task_boards_column_id == task_boards_column_id) |
                (TaskBoardNotification.task_boards_column_id.is_(None))
            )
        else:
            q = q.filter(TaskBoardNotification.task_boards_column_id.is_(None))
        row = q.first()
        if not row:
            return False
        if row.expaired_at is None:
            return True
        return row.expaired_at > msk_now()

    def update(self, notification_id: int, payload: dict) -> TaskBoardNotification | None:
        row = self.get_by_id(notification_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, notification_id: int) -> bool:
        row = self.get_by_id(notification_id)
        if row:
            self.db.delete(row)
            self.db.commit()
            return True
        return False
