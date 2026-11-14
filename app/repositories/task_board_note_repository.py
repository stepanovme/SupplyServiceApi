import uuid

from sqlalchemy.orm import Session

from app.models.task import TaskBoardNote


class TaskBoardNoteRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(self, payload: dict) -> TaskBoardNote:
        payload["id"] = str(uuid.uuid4())
        row = TaskBoardNote(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_by_id(self, note_id: str) -> TaskBoardNote | None:
        return self.db.query(TaskBoardNote).filter(TaskBoardNote.id == note_id).first()

    def get_by_board(self, task_board_id: str) -> list[TaskBoardNote]:
        return (
            self.db.query(TaskBoardNote)
            .filter(TaskBoardNote.task_board_id == task_board_id)
            .order_by(TaskBoardNote.created_at.desc())
            .all()
        )

    def update(self, note_id: str, payload: dict) -> TaskBoardNote | None:
        row = self.get_by_id(note_id)
        if row:
            for key, value in payload.items():
                setattr(row, key, value)
            self.db.commit()
            self.db.refresh(row)
        return row

    def delete(self, note_id: str) -> bool:
        row = self.get_by_id(note_id)
        if row:
            self.db.delete(row)
            self.db.commit()
            return True
        return False
