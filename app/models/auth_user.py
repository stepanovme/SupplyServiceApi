from sqlalchemy import Column, String

from app.database import AuthBase


class AuthUser(AuthBase):
    __tablename__ = "users"

    id = Column(String(36), primary_key=True)
    name = Column(String(100))
    surname = Column(String(100))
    patronymic = Column(String(100))
