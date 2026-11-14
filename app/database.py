import os
from datetime import datetime, timedelta
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


def msk_now():
    return datetime.utcnow() + timedelta(hours=3)

load_dotenv()

# Each named tenant has its own connection pools, shared by its configured hosts.
import re
from contextvars import ContextVar
from urllib.parse import urlsplit
from sqlalchemy.engine import URL
from app.tenant_config import load_tenants

current_tenant = ContextVar("current_tenant", default=os.getenv("TENANT_CLI_SITE"))
_tenant_config, _tenant_hosts = load_tenants()

def _make_engines(config):
    engines = {}
    for kind, key in (("auth", "DB_NAME"), ("supply", "SUPPLY_DB_NAME"), ("reference", "REFERENCE_DB_NAME")):
        name = config.get(key) or os.getenv(key)
        if not name:
            raise ValueError(f"{key} must be configured")
        url = URL.create("mysql+pymysql", username=config.get("DB_USER", os.getenv("DB_USER")),
                         password=config.get("DB_PASSWORD", os.getenv("DB_PASSWORD")),
                         host=config.get("DB_HOST", os.getenv("DB_HOST")),
                         port=int(config.get("DB_PORT") or os.getenv("DB_PORT") or 3306), database=name)
        engines[kind] = create_engine(url, pool_recycle=3600, pool_pre_ping=True)
    warehouse = config.get("WAREHOUSE_DB_NAME") if _tenant_config else os.getenv("WAREHOUSE_DB_NAME")
    if warehouse and not re.fullmatch(r"[A-Za-z0-9_$]+", warehouse):
        raise ValueError("Invalid WAREHOUSE_DB_NAME")
    engines["warehouse"] = warehouse
    return engines


_engines = {name: _make_engines(config) for name, config in _tenant_config.items()}
if not _engines:
    _engines["default"] = _make_engines({})
_cli_site = os.getenv("TENANT_CLI_SITE")
if _cli_site and _cli_site not in _engines:
    raise ValueError("TENANT_CLI_SITE is not configured in TENANTS")
_default = _engines[_cli_site] if _cli_site else next(iter(_engines.values()))
auth_engine, supply_engine, reference_engine = (_default[k] for k in ("auth", "supply", "reference"))


def resolve_tenant(scope):
    if not _tenant_config:
        return "default"
    headers = dict(scope.get("headers", []))
    origin = headers.get(b"origin", b"").decode("latin1")
    if origin:
        parsed = urlsplit(origin)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password:
            return None
        host = parsed.hostname.lower()
    else:
        host = headers.get(b"host", b"").decode("latin1").split(":", 1)[0].lower()
    return _tenant_hosts.get(host)


def tenant_engine(kind):
    tenant = current_tenant.get()
    if tenant is None and _tenant_config:
        raise RuntimeError("Tenant context is required")
    return _engines[tenant or "default"][kind]


def tenant_cookie_name():
    tenant = current_tenant.get()
    if tenant is None and _tenant_config:
        raise RuntimeError("Tenant context is required")
    return _tenant_config.get(tenant, {}).get("COOKIE_NAME", "session")


def AuthSessionLocal(**kwargs):
    return Session(bind=tenant_engine("auth"), autoflush=False, **kwargs)


def SupplySessionLocal(**kwargs):
    return Session(bind=tenant_engine("supply"), autoflush=False, **kwargs)


def ReferenceSessionLocal(**kwargs):
    return Session(bind=tenant_engine("reference"), autoflush=False, **kwargs)


class AuthBase(DeclarativeBase):
    pass


class SupplyBase(DeclarativeBase):
    pass


class ReferenceBase(DeclarativeBase):
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


def get_reference_db() -> Session:  # pyright: ignore[reportInvalidTypeForm]
    db = ReferenceSessionLocal()
    try:
        yield db  # pyright: ignore[reportReturnType]
    finally:
        db.close()


DbAuthSession = Annotated[Session, Depends(get_auth_db)]
DbSupplySession = Annotated[Session, Depends(get_supply_db)]
DbReferenceSession = Annotated[Session, Depends(get_reference_db)]
