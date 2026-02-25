import uuid
from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Enum as SqlEnum, String

from app.database import SupplyBase


class ProjectUserRoleType(str, Enum):
    SUPPLY_MANAGER = "Supply manager"
    REQUEST_APPROVER = "Request approver"
    BUDGET_OWNER = "Budget owner"
    PAYMENT_PLANNER = "Payment planner"
    DISBURSEMENT_OFFICER = "Disbursement officer"
    REQUESTER = "Requester"
    INVOICE_APPROVER = "Invoice approver"
    BUDGET_APPROVER = "Budget approver"
    PAYMENT_PROCESSOR = "Payment processor"


class ProjectUserRole(SupplyBase):
    __tablename__ = "project_user_roles"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    object_levels_id = Column(String(36), nullable=False, index=True)
    user_id = Column(String(36), nullable=False, index=True)
    role = Column(
        SqlEnum(ProjectUserRoleType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )


class ProjectUserRoleCreate(BaseModel):
    id: str | None = Field(default=None)
    object_levels_id: str = Field()
    user_id: str = Field()
    role: ProjectUserRoleType = Field()
