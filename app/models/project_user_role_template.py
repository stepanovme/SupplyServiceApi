from enum import Enum

from pydantic import BaseModel, Field
from sqlalchemy import Column, Enum as SqlEnum, Integer, String

from app.database import SupplyBase


class ProjectUserRoleTemplateType(str, Enum):
    SUPPLY_MANAGER = "Supply manager"
    REQUEST_APPROVER = "Request approver"
    BUDGET_OWNER = "Budget owner"
    PAYMENT_PLANNER = "Payment planner"
    DISBURSEMENT_OFFICER = "Disbursement officer"
    REQUESTER = "Requester"
    INVOICE_APPROVER = "Invoice approver"
    BUDGET_APPROVER = "Budget approver"
    PAYMENT_PROCESSOR = "Payment processor"


class ProjectUserRoleTemplate(SupplyBase):
    __tablename__ = "project_user_roles_template"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=True, index=True)
    departament_id = Column(Integer, nullable=True)
    role = Column(
        SqlEnum(ProjectUserRoleTemplateType, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
    )


class ProjectUserRoleTemplateCreate(BaseModel):
    user_id: str | None = Field(default=None)
    departament_id: int | None = Field(default=None)
    role: ProjectUserRoleTemplateType = Field()


class ProjectUserRoleTemplateUpdate(BaseModel):
    user_id: str | None = Field(default=None)
    departament_id: int | None = Field(default=None)
    role: ProjectUserRoleTemplateType | None = Field(default=None)
