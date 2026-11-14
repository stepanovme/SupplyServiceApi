from sqlalchemy import Column, DateTime, String, text

from app.database import SupplyBase


class UserCompanyPosition(SupplyBase):
    """Company and position assigned to a user within this site."""

    __tablename__ = "user_company_positions"

    user_id = Column(String(36), primary_key=True)
    company_id = Column(String(36), nullable=False, index=True)
    position = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP"))
    updated_at = Column(DateTime, nullable=False, server_default=text("CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"))
