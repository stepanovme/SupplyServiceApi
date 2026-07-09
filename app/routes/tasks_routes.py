import os
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.task import (
    TaskAccomplishmentCreate,
    TaskAccomplishmentUpdate,
    TaskBoardColumnCreate,
    TaskBoardColumnUpdate,
    TaskBoardCreate,
    TaskBoardUpdate,
    TaskBoardUserRoleCreate,
    TaskBoardUserRoleUpdate,
    TaskCreate,
    TaskItemCreate,
    TaskItemUpdate,
    TaskResultCreate,
    TaskResultUpdate,
    TaskTagCreate,
    TaskTagUpdate,
    TaskUpdate,
    TaskUserRoleCreate,
    TaskUserRoleUpdate,
)
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.repositories.task_repository import TaskRepository
from app.services.task_service import BASE_TASK_FILES_DIR, TaskService

tasks_router = APIRouter(prefix="", tags=["Tasks"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
    reference_db: DbReferenceSession | None = None,
) -> TaskService:
    return TaskService(
        TaskRepository(supply_db),
        AuthUserRepository(auth_db) if auth_db else None,
        ReferenceObjectRepository(reference_db) if reference_db else None,
    )


# --- TaskLog ---

@tasks_router.get("/task-logs", status_code=status.HTTP_200_OK)
def get_task_logs(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    log_object_id: str | None = Query(default=None),
    created_by: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_logs(log_object_id, created_by)


# --- Task ---

@tasks_router.get("/tasks/my", status_code=status.HTTP_200_OK)
def get_my_tasks(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    role: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db, reference_db).get_my_tasks(_session.user_id, role)


@tasks_router.get("/tasks", status_code=status.HTTP_200_OK)
def get_tasks(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
    connection_type: str | None = None,
    connection_id: str | None = None,
):
    return build_service(supply_db, auth_db, reference_db).get_tasks(connection_type, connection_id)


@tasks_router.get("/tasks/incomplete-count", status_code=status.HTTP_200_OK)
def get_tasks_incomplete_count(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return {"count": build_service(supply_db).get_incomplete_count(_session.user_id)}


@tasks_router.get("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def get_task(
    task_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_task(task_id)


@tasks_router.post("/tasks", status_code=status.HTTP_201_CREATED)
def create_task(
    payload: TaskCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_task(payload, _session.user_id)


@tasks_router.patch("/tasks/{task_id}", status_code=status.HTTP_200_OK)
def update_task(
    task_id: str,
    payload: TaskUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_task(task_id, payload, _session.user_id)


@tasks_router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(
    task_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_task(task_id, _session.user_id)
    return None


# --- TaskItem ---

@tasks_router.get("/task-items", status_code=status.HTTP_200_OK)
def get_task_items(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    task_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_items(task_id)


@tasks_router.get("/task-items/{item_id}", status_code=status.HTTP_200_OK)
def get_task_item(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_item(item_id)


@tasks_router.post("/task-items", status_code=status.HTTP_201_CREATED)
def create_task_item(
    payload: TaskItemCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_item(payload, _session.user_id)


@tasks_router.patch("/task-items/{item_id}", status_code=status.HTTP_200_OK)
def update_task_item(
    item_id: str,
    payload: TaskItemUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_item(item_id, payload, _session.user_id)


@tasks_router.delete("/task-items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_item(
    item_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_item(item_id, _session.user_id)
    return None


# --- TaskUserRole ---

@tasks_router.get("/task-user-roles", status_code=status.HTTP_200_OK)
def get_task_user_roles(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    task_id: str | None = Query(default=None),
    task_item_id: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_user_roles(task_id, task_item_id)


@tasks_router.get("/task-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def get_task_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_user_role(role_id)


@tasks_router.post("/task-user-roles", status_code=status.HTTP_201_CREATED)
def create_task_user_role(
    payload: TaskUserRoleCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_user_role(payload, _session.user_id)


@tasks_router.patch("/task-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def update_task_user_role(
    role_id: str,
    payload: TaskUserRoleUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_user_role(role_id, payload, _session.user_id)


@tasks_router.delete("/task-user-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).delete_user_role(role_id, _session.user_id)
    return None


# --- TaskTag ---

@tasks_router.get("/task-tags", status_code=status.HTTP_200_OK)
def get_task_tags(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    task_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_tags(task_id)


@tasks_router.get("/task-tags/{tag_id}", status_code=status.HTTP_200_OK)
def get_task_tag(
    tag_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_tag(tag_id)


@tasks_router.post("/task-tags", status_code=status.HTTP_201_CREATED)
def create_task_tag(
    payload: TaskTagCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_tag(payload, _session.user_id)


@tasks_router.patch("/task-tags/{tag_id}", status_code=status.HTTP_200_OK)
def update_task_tag(
    tag_id: str,
    payload: TaskTagUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_tag(tag_id, payload, _session.user_id)


@tasks_router.delete("/task-tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_tag(
    tag_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).delete_tag(tag_id, _session.user_id)
    return None


# --- TaskAccomplishment ---

@tasks_router.get("/task-accomplishments", status_code=status.HTTP_200_OK)
def get_task_accomplishments(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    task_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_accomplishments(task_id)


@tasks_router.get("/task-accomplishments/{acc_id}", status_code=status.HTTP_200_OK)
def get_task_accomplishment(
    acc_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_accomplishment(acc_id)


@tasks_router.post("/task-accomplishments", status_code=status.HTTP_201_CREATED)
def create_task_accomplishment(
    payload: TaskAccomplishmentCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_accomplishment(payload, _session.user_id)


@tasks_router.patch("/task-accomplishments/{acc_id}", status_code=status.HTTP_200_OK)
def update_task_accomplishment(
    acc_id: str,
    payload: TaskAccomplishmentUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_accomplishment(acc_id, payload, _session.user_id)


@tasks_router.delete("/task-accomplishments/{acc_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_accomplishment(
    acc_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_accomplishment(acc_id, _session.user_id)
    return None


# --- TaskResult ---

@tasks_router.get("/task-results", status_code=status.HTTP_200_OK)
def get_task_results(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    task_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_results(task_id)


@tasks_router.get("/task-results/{result_id}", status_code=status.HTTP_200_OK)
def get_task_result(
    result_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_result(result_id)


@tasks_router.post("/task-results", status_code=status.HTTP_201_CREATED)
def create_task_result(
    payload: TaskResultCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_result(payload, _session.user_id)


@tasks_router.patch("/task-results/{result_id}", status_code=status.HTTP_200_OK)
def update_task_result(
    result_id: str,
    payload: TaskResultUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_result(result_id, payload, _session.user_id)


@tasks_router.delete("/task-results/{result_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_result(
    result_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_result(result_id, _session.user_id)
    return None


# --- TaskFile ---

@tasks_router.get("/task-files", status_code=status.HTTP_200_OK)
def get_task_files(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    task_id: str | None = Query(default=None),
    task_result_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_files(task_id, task_result_id)


@tasks_router.get("/task-files/{file_id}", status_code=status.HTTP_200_OK)
def get_task_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_file(file_id)


@tasks_router.post("/task-files", status_code=status.HTTP_201_CREATED)
async def upload_task_files(
    files: Annotated[list[UploadFile], File(...)],
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    task_id: str | None = Form(default=None),
    task_result_id: str | None = Form(default=None),
):
    service = build_service(supply_db, auth_db)
    results = []
    for f in files:
        file_bytes = await f.read()
        results.append(service.upload(
            original_name=f.filename or "file",
            file_bytes=file_bytes,
            uploaded_by=_session.user_id,
            task_id=task_id,
            task_result_id=task_result_id,
        ))
    return results


@tasks_router.delete("/task-files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_file(
    file_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    build_service(supply_db, auth_db).delete_file(file_id, _session.user_id)
    return None


@tasks_router.get("/task-files/{file_id}/download", status_code=status.HTTP_200_OK)
def download_task_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path, original_name = build_service(supply_db).get_download(file_id)
    return FileResponse(file_path, filename=original_name)


@tasks_router.get("/task-files/{file_id}/preview", status_code=status.HTTP_200_OK)
def preview_task_file(
    file_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    file_path = build_service(supply_db).get_preview(file_id)
    return FileResponse(file_path, media_type="application/pdf")


# --- TaskBoard ---

@tasks_router.get("/task-boards/my", status_code=status.HTTP_200_OK)
def get_my_task_boards(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_my_boards(_session.user_id)


@tasks_router.get("/task-boards", status_code=status.HTTP_200_OK)
def get_task_boards(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_boards()


@tasks_router.get("/task-boards/{board_id}/tasks", status_code=status.HTTP_200_OK)
def get_task_board_tasks(
    board_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_board_tasks(board_id, _session.user_id)


@tasks_router.get("/task-boards/{board_id}", status_code=status.HTTP_200_OK)
def get_task_board(
    board_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).get_board(board_id)


@tasks_router.post("/task-boards", status_code=status.HTTP_201_CREATED)
def create_task_board(
    payload: TaskBoardCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db, reference_db).create_board(payload, _session.user_id)


@tasks_router.patch("/task-boards/{board_id}", status_code=status.HTTP_200_OK)
def update_task_board(
    board_id: str,
    payload: TaskBoardUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_board(board_id, payload, _session.user_id)


@tasks_router.delete("/task-boards/{board_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_board(
    board_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_board(board_id, _session.user_id)
    return None


# --- TaskBoardColumn ---

@tasks_router.get("/task-board-columns", status_code=status.HTTP_200_OK)
def get_task_board_columns(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    task_board_id: str | None = Query(default=None),
):
    return build_service(supply_db).get_board_columns(task_board_id)


@tasks_router.get("/task-board-columns/{column_id}", status_code=status.HTTP_200_OK)
def get_task_board_column(
    column_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).get_board_column(column_id)


@tasks_router.post("/task-board-columns", status_code=status.HTTP_201_CREATED)
def create_task_board_column(
    payload: TaskBoardColumnCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_board_column(payload, _session.user_id)


@tasks_router.patch("/task-board-columns/{column_id}", status_code=status.HTTP_200_OK)
def update_task_board_column(
    column_id: str,
    payload: TaskBoardColumnUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_board_column(column_id, payload, _session.user_id)


@tasks_router.delete("/task-board-columns/{column_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_board_column(
    column_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_board_column(column_id, _session.user_id)
    return None


# --- TaskBoardUserRole ---

@tasks_router.get("/task-boards-user-roles", status_code=status.HTTP_200_OK)
def get_task_board_user_roles(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
    task_boards_id: str | None = Query(default=None),
):
    return build_service(supply_db, auth_db).get_board_user_roles(task_boards_id)


@tasks_router.get("/task-boards-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def get_task_board_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_board_user_role(role_id)


@tasks_router.post("/task-boards-user-roles", status_code=status.HTTP_201_CREATED)
def create_task_board_user_role(
    payload: TaskBoardUserRoleCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create_board_user_role(payload, _session.user_id)


@tasks_router.patch("/task-boards-user-roles/{role_id}", status_code=status.HTTP_200_OK)
def update_task_board_user_role(
    role_id: str,
    payload: TaskBoardUserRoleUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_board_user_role(role_id, payload, _session.user_id)


@tasks_router.delete("/task-boards-user-roles/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task_board_user_role(
    role_id: str,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_board_user_role(role_id, _session.user_id)
    return None
