from fastapi import APIRouter, Depends, HTTPException, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.task import TaskBoardNoteCreate, TaskBoardNoteUpdate
from app.repositories.task_board_note_repository import TaskBoardNoteRepository
from app.services.task_board_note_service import TaskBoardNoteService

task_board_note_router = APIRouter(prefix="/task-board-notes", tags=["Task Board Notes"])


def build_service(db: DbSupplySession) -> TaskBoardNoteService:
    return TaskBoardNoteService(TaskBoardNoteRepository(db))


@task_board_note_router.get("")
def get_notes_by_board(
    task_board_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_by_board(task_board_id)


@task_board_note_router.get("/{note_id}")
def get_note(
    note_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).get_by_id(note_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return result


@task_board_note_router.post("", status_code=status.HTTP_201_CREATED)
def create_note(
    payload: TaskBoardNoteCreate,
    db: DbSupplySession,
    session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload, str(session.user_id))


@task_board_note_router.patch("/{note_id}")
def update_note(
    note_id: str,
    payload: TaskBoardNoteUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).update(note_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return result


@task_board_note_router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_note(
    note_id: str,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    deleted = build_service(db).delete(note_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return None
