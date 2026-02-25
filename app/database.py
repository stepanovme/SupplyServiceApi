import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

load_dotenv()

AUTH_DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

SUPPLY_DB_NAME = os.getenv("SUPPLY_DB_NAME", "supply_service")
SUPPLY_DATABASE_URL = (
    f"mysql+pymysql://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}@"
    f"{os.getenv('DB_HOST')}:{os.getenv('DB_PORT')}/{SUPPLY_DB_NAME}"
)

auth_engine = create_engine(AUTH_DATABASE_URL)
supply_engine = create_engine(SUPPLY_DATABASE_URL)

AuthSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=auth_engine)
SupplySessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=supply_engine)


class AuthBase(DeclarativeBase):
    pass


class SupplyBase(DeclarativeBase):
    pass


def get_auth_db() -> Session:  # pyright: ignore[reportInvalidTypeForm]
    db = AuthSessionLocal()
    try:
        yield db  # pyright: ignore[reportReturnType]
    finally:
        db.close()


def get_supply_db() -> Session:  # pyright: ignore[reportInvalidTypeForm]
    db = SupplySessionLocal()
    try:
        yield db  # pyright: ignore[reportReturnType]
    finally:
        db.close()


DbAuthSession = Annotated[Session, Depends(get_auth_db)]
DbSupplySession = Annotated[Session, Depends(get_supply_db)]
