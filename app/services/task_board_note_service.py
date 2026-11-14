from app.repositories.task_board_note_repository import TaskBoardNoteRepository
from app.models.task import TaskBoardNoteCreate, TaskBoardNoteUpdate


class TaskBoardNoteService:
    def __init__(self, repo: TaskBoardNoteRepository) -> None:
        self.repo = repo

    def create(self, payload: TaskBoardNoteCreate, created_by: str) -> dict:
        data = payload.model_dump()
        data["created_by"] = created_by
        row = self.repo.create(data)
        return self._serialize(row)

    def get_by_id(self, note_id: str) -> dict | None:
        row = self.repo.get_by_id(note_id)
        return self._serialize(row) if row else None

    def get_by_board(self, task_board_id: str) -> list[dict]:
        rows = self.repo.get_by_board(task_board_id)
        return [self._serialize(r) for r in rows]

    def update(self, note_id: str, payload: TaskBoardNoteUpdate) -> dict | None:
        data = payload.model_dump(exclude_unset=True)
        row = self.repo.update(note_id, data)
        return self._serialize(row) if row else None

    def delete(self, note_id: str) -> bool:
        return self.repo.delete(note_id)

    def _serialize(self, row) -> dict:
        return {
            "id": row.id,
            "task_board_id": row.task_board_id,
            "note": row.note,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by": row.created_by,
        }
