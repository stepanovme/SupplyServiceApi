from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.session import SessionDB
from app.models.task import TaskBoardNotificationCreate, TaskBoardNotificationUpdate
from app.repositories.task_board_notification_repository import TaskBoardNotificationRepository
from app.services.task_board_notification_service import TaskBoardNotificationService

task_board_notification_router = APIRouter(prefix="/task-board-notifications", tags=["Task Board Notifications"])


def build_service(db: DbSupplySession) -> TaskBoardNotificationService:
    return TaskBoardNotificationService(TaskBoardNotificationRepository(db))


@task_board_notification_router.get("/my")
def get_my_notifications(
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).get_by_user(str(_session.user_id))


@task_board_notification_router.get("")
def get_notifications(
    db: DbSupplySession,
    task_board_id: str | None = Query(default=None),
    task_boards_column_id: str | None = Query(default=None),
    user_id: str | None = Query(default=None),
):
    return build_service(db).get_list(
        task_board_id=task_board_id,
        task_boards_column_id=task_boards_column_id,
        user_id=user_id,
    )


@task_board_notification_router.get("/{notification_id}")
def get_notification(
    notification_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).get_by_id(notification_id)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return result


@task_board_notification_router.post("", status_code=status.HTTP_201_CREATED)
def create_notification(
    payload: TaskBoardNotificationCreate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    return build_service(db).create(payload)


@task_board_notification_router.patch("/{notification_id}")
def update_notification(
    notification_id: int,
    payload: TaskBoardNotificationUpdate,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    result = build_service(db).update(notification_id, payload)
    if not result:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return result


@task_board_notification_router.delete("/{notification_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_notification(
    notification_id: int,
    db: DbSupplySession,
    _session: SessionDB = Depends(get_session),
):
    deleted = build_service(db).delete(notification_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    return None
