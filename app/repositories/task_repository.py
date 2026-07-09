import uuid

from sqlalchemy import union
from sqlalchemy.orm import Session

from app.models.chat import Chat
from app.models.contract import ContractLog
from app.models.supply_request import StatusRef
from app.models.task import (
    Task,
    TaskAccomplishment,
    TaskBoard,
    TaskBoardColumn,
    TaskBoardUserRole,
    TaskFile,
    TaskItem,
    TaskResult,
    TaskTag,
    TaskUserRole,
    msk_now,
)


class TaskRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Task ---

    def get_task_by_id(self, task_id: str) -> Task | None:
        return self.db.query(Task).filter(Task.id == task_id).first()

    def get_tasks(self) -> list[Task]:
        return self.db.query(Task).order_by(Task.created_at.desc()).all()

    def get_tasks_by_connection(self, connection_id: str, connection_type: str) -> list[Task]:
        return self.db.query(Task).filter(
            Task.connection_id == connection_id,
            Task.connection_type == connection_type,
        ).order_by(Task.created_at.desc()).all()

    def get_task_ids_by_user(self, user_id: str, role: str | None = None) -> list[str]:
        if role == "creator":
            rows = self.db.query(Task.id).filter(Task.created_by == user_id).all()
            return [row[0] for row in rows]
        if role is not None:
            rows = self.db.query(TaskUserRole.task_id).filter(
                TaskUserRole.user_id == user_id,
                TaskUserRole.role == role,
            ).all()
            return [row[0] for row in rows if row[0] is not None]
        created_q = self.db.query(Task.id).filter(Task.created_by == user_id)
        role_q = self.db.query(TaskUserRole.task_id).filter(TaskUserRole.user_id == user_id)
        union_q = union(created_q, role_q).subquery()
        rows = self.db.query(Task.id).filter(Task.id.in_(union_q)).all()
        return [row[0] for row in rows]

    def create_task(self, payload: dict) -> Task:
        payload["id"] = payload.get("id", str(uuid.uuid4()))
        row = Task(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_task(self, row: Task) -> Task:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_task(self, row: Task) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskItem ---

    def get_items(self, task_id: str | None = None) -> list[TaskItem]:
        q = self.db.query(TaskItem)
        if task_id is not None:
            q = q.filter(TaskItem.task_id == task_id)
        return q.order_by(TaskItem.num.asc()).all()

    def get_item_by_id(self, item_id: str) -> TaskItem | None:
        return self.db.query(TaskItem).filter(TaskItem.id == item_id).first()

    def create_item(self, payload: dict) -> TaskItem:
        payload["id"] = str(uuid.uuid4())
        row = TaskItem(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_item(self, row: TaskItem) -> TaskItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_item(self, row: TaskItem) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskUserRole ---

    def get_user_roles(self, task_id: str | None = None, task_item_id: str | None = None, role: str | None = None) -> list[TaskUserRole]:
        q = self.db.query(TaskUserRole)
        if task_id is not None:
            q = q.filter(TaskUserRole.task_id == task_id)
        if task_item_id is not None:
            q = q.filter(TaskUserRole.task_item_id == task_item_id)
        if role is not None:
            q = q.filter(TaskUserRole.role == role)
        return q.order_by(TaskUserRole.created_at.desc()).all()

    def get_user_role_by_id(self, role_id: str) -> TaskUserRole | None:
        return self.db.query(TaskUserRole).filter(TaskUserRole.id == role_id).first()

    def create_user_role(self, payload: dict) -> TaskUserRole:
        payload["id"] = str(uuid.uuid4())
        row = TaskUserRole(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_user_role(self, row: TaskUserRole) -> TaskUserRole:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user_role(self, row: TaskUserRole) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskResult ---

    def get_results(self, task_id: str | None = None) -> list[TaskResult]:
        q = self.db.query(TaskResult)
        if task_id is not None:
            q = q.filter(TaskResult.task_id == task_id)
        return q.order_by(TaskResult.created_at.desc()).all()

    def get_result_by_id(self, result_id: str) -> TaskResult | None:
        return self.db.query(TaskResult).filter(TaskResult.id == result_id).first()

    def create_result(self, payload: dict) -> TaskResult:
        payload["id"] = str(uuid.uuid4())
        row = TaskResult(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_result(self, row: TaskResult) -> TaskResult:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_result(self, row: TaskResult) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskFile ---

    def get_files(self, task_id: str | None = None, task_result_id: str | None = None) -> list[TaskFile]:
        q = self.db.query(TaskFile)
        if task_id is not None:
            q = q.filter(TaskFile.task_id == task_id)
        if task_result_id is not None:
            q = q.filter(TaskFile.task_result_id == task_result_id)
        return q.order_by(TaskFile.uploaded_at.desc()).all()

    def get_file_by_id(self, file_id: str) -> TaskFile | None:
        return self.db.query(TaskFile).filter(TaskFile.id == file_id).first()

    def create_file(self, payload: dict) -> TaskFile:
        payload["id"] = str(uuid.uuid4())
        row = TaskFile(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_file(self, row: TaskFile) -> TaskFile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: TaskFile) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskBoard ---

    def get_board_by_id(self, board_id: str) -> TaskBoard | None:
        return self.db.query(TaskBoard).filter(TaskBoard.id == board_id).first()

    def get_boards(self) -> list[TaskBoard]:
        return self.db.query(TaskBoard).order_by(TaskBoard.created_at.desc()).all()

    def get_board_ids_by_user(self, user_id: str) -> list[str]:
        created_q = self.db.query(TaskBoard.id).filter(TaskBoard.created_by == user_id)
        role_q = self.db.query(TaskBoardUserRole.task_boards_id).filter(TaskBoardUserRole.user_id == user_id)
        union_q = union(created_q, role_q).subquery()
        rows = self.db.query(TaskBoard.id).filter(TaskBoard.id.in_(union_q)).all()
        return [row[0] for row in rows]

    def create_board(self, payload: dict) -> TaskBoard:
        payload["id"] = str(uuid.uuid4())
        row = TaskBoard(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_board(self, row: TaskBoard) -> TaskBoard:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_board(self, row: TaskBoard) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskBoardColumn ---

    def get_board_columns(self, task_board_id: str | None = None) -> list[TaskBoardColumn]:
        q = self.db.query(TaskBoardColumn)
        if task_board_id is not None:
            q = q.filter(TaskBoardColumn.task_board_id == task_board_id)
        return q.order_by(TaskBoardColumn.num.asc()).all()

    def get_board_column_by_id(self, column_id: str) -> TaskBoardColumn | None:
        return self.db.query(TaskBoardColumn).filter(TaskBoardColumn.id == column_id).first()

    def create_board_column(self, payload: dict) -> TaskBoardColumn:
        payload["id"] = str(uuid.uuid4())
        row = TaskBoardColumn(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_board_column(self, row: TaskBoardColumn) -> TaskBoardColumn:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_board_column(self, row: TaskBoardColumn) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskBoardUserRole ---

    def get_board_user_roles(self, task_boards_id: str | None = None, role: str | None = None) -> list[TaskBoardUserRole]:
        q = self.db.query(TaskBoardUserRole)
        if task_boards_id is not None:
            q = q.filter(TaskBoardUserRole.task_boards_id == task_boards_id)
        if role is not None:
            q = q.filter(TaskBoardUserRole.role == role)
        return q.order_by(TaskBoardUserRole.created_at.desc()).all()

    def get_board_user_role_by_id(self, role_id: str) -> TaskBoardUserRole | None:
        return self.db.query(TaskBoardUserRole).filter(TaskBoardUserRole.id == role_id).first()

    def create_board_user_role(self, payload: dict) -> TaskBoardUserRole:
        payload["id"] = str(uuid.uuid4())
        row = TaskBoardUserRole(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_board_user_role(self, row: TaskBoardUserRole) -> TaskBoardUserRole:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_board_user_role(self, row: TaskBoardUserRole) -> None:
        self.db.delete(row)
        self.db.commit()

    def count_incomplete_tasks(self, user_id: str) -> int:
        from sqlalchemy import not_
        completed_status = "1ff32c4b-1312-11f1-aa8c-bc241127d0bd"

        role_ids = self.db.query(TaskUserRole.task_id).filter(
            TaskUserRole.user_id == user_id,
            TaskUserRole.role.in_(["responsible", "co-executor"]),
        ).all()
        my_ids = list({row[0] for row in role_ids if row[0] is not None})
        if not my_ids:
            return 0

        completed_by_status = self.db.query(Task.id).filter(
            Task.id.in_(my_ids),
            Task.status_id == completed_status,
        )
        completed_by_acc = self.db.query(TaskAccomplishment.task_id).filter(
            TaskAccomplishment.task_id.in_(my_ids),
            TaskAccomplishment.created_by == user_id,
            TaskAccomplishment.status_id == completed_status,
        )
        completed_ids_q = union(completed_by_status, completed_by_acc).subquery()

        incomplete = self.db.query(Task.id).filter(
            Task.id.in_(my_ids),
            not_(Task.id.in_(completed_ids_q)),
        )
        return incomplete.count()

    # --- TaskAccomplishment ---

    def get_accomplishments(self, task_id: str | None = None) -> list[TaskAccomplishment]:
        q = self.db.query(TaskAccomplishment)
        if task_id is not None:
            q = q.filter(TaskAccomplishment.task_id == task_id)
        return q.order_by(TaskAccomplishment.date_start.desc()).all()

    def get_accomplishment_by_id(self, acc_id: str) -> TaskAccomplishment | None:
        return self.db.query(TaskAccomplishment).filter(TaskAccomplishment.id == acc_id).first()

    def create_accomplishment(self, payload: dict) -> TaskAccomplishment:
        payload["id"] = str(uuid.uuid4())
        row = TaskAccomplishment(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_accomplishment(self, row: TaskAccomplishment) -> TaskAccomplishment:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_accomplishment(self, row: TaskAccomplishment) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TaskTag ---

    def get_tags(self, task_id: str | None = None) -> list[TaskTag]:
        q = self.db.query(TaskTag)
        if task_id is not None:
            q = q.filter(TaskTag.task_id == task_id)
        return q.order_by(TaskTag.created_at.asc()).all()

    def get_tag_by_id(self, tag_id: str) -> TaskTag | None:
        return self.db.query(TaskTag).filter(TaskTag.id == tag_id).first()

    def create_tag(self, payload: dict) -> TaskTag:
        payload["id"] = str(uuid.uuid4())
        row = TaskTag(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_tag(self, row: TaskTag) -> TaskTag:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_tag(self, row: TaskTag) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- Connection lookups ---

    def get_letter_by_id(self, letter_id: int):
        from app.models.letter import Letter
        return self.db.query(Letter).filter(Letter.id == letter_id).first()

    def get_contract_by_id(self, contract_id: int):
        from app.models.contract import Contract
        return self.db.query(Contract).filter(Contract.id == contract_id).first()

    def get_document_type_name(self, doc_type_id: str) -> str | None:
        from app.models.contract import DocumentType
        row = self.db.query(DocumentType.name).filter(DocumentType.id == doc_type_id).first()
        return row[0] if row else None

    def get_request_by_id(self, request_id: int):
        from app.models.supply_request import SupplyRequest
        return self.db.query(SupplyRequest).filter(SupplyRequest.id == request_id).first()

    def get_invoice_by_id(self, invoice_id: int):
        from app.models.invoice import Invoice
        return self.db.query(Invoice).filter(Invoice.id == invoice_id).first()

    def get_deal_by_id(self, deal_id: str):
        from app.models.deal import Deal
        return self.db.query(Deal).filter(Deal.id == deal_id).first()

    def get_warehouse_by_id(self, warehouse_id: str):
        from app.models.warehouse import Warehouse
        return self.db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()

    def get_specification_by_id(self, spec_id: str):
        from app.models.specification import Specification
        return self.db.query(Specification).filter(Specification.id == spec_id).first()

    # --- Logging ---

    def create_log(self, log_object_id: str, message: str, created_by: str) -> ContractLog:
        row = ContractLog(
            id=str(uuid.uuid4()),
            log_object_id=log_object_id,
            log_object_type="task",
            message=message,
            created_at=msk_now(),
            created_by=created_by,
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_chat_id_by_task_id(self, task_id: str) -> int | None:
        row = self.db.query(Chat.id).filter(Chat.task_id == task_id).first()
        return row[0] if row else None

    def get_status_name(self, status_id: str | None) -> str | None:
        if not status_id:
            return None
        row = self.db.query(StatusRef).filter(StatusRef.id == status_id).first()
        return row.name if row else None

    def delete_logs_by_task(self, task_id: str) -> None:
        self.db.query(ContractLog).filter(
            ContractLog.log_object_id == task_id,
            ContractLog.log_object_type == "task",
        ).delete()
        self.db.commit()

    def get_logs(
        self,
        log_object_id: str | None = None,
        created_by: str | None = None,
    ) -> list[ContractLog]:
        q = self.db.query(ContractLog).filter(ContractLog.log_object_type == "task")
        if log_object_id is not None:
            q = q.filter(ContractLog.log_object_id == log_object_id)
        if created_by is not None:
            q = q.filter(ContractLog.created_by == created_by)
        return q.order_by(ContractLog.created_at.desc()).all()
