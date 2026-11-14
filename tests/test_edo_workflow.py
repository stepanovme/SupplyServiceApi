from contextlib import contextmanager
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.dialects.mysql import LONGBLOB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.database import current_tenant, get_supply_db
from app.models.edo_exchange import EdoBase, EdoParticipant
from app.routes import edo_routes
from app.services.edo_store import new_id


@compiles(LONGBLOB, "sqlite")
def sqlite_blob(_type, _compiler, **_kwargs):
    return "BLOB"


def test_exchange_lifecycle(tmp_path, monkeypatch):
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    EdoBase.metadata.create_all(engine)
    first, second, third = new_id(), new_id(), new_id()
    with Session(engine) as db, db.begin():
        db.add_all([EdoParticipant(id=first, tenant="FIRST"), EdoParticipant(id=second, tenant="SECOND"),
                    EdoParticipant(id=third, tenant="THIRD")])

    @contextmanager
    def hub_session():
        with Session(engine, expire_on_commit=False) as db, db.begin():
            yield db

    monkeypatch.setattr(edo_routes, "hub_session", hub_session)
    file_path = tmp_path / "contract.txt"
    file_path.write_bytes(b"original contract")
    source = SimpleNamespace(created_by="user", num="1", date=None, sum=10, name="Contract", comment=None)
    attachment = SimpleNamespace(id="file-1", file_path=str(file_path), original_name="contract.txt")

    class SourceDB:
        def get(self, model, key):
            return source
        def scalar(self, query):
            return None
        def scalars(self, query):
            return SimpleNamespace(all=lambda: [attachment])

    app = FastAPI()
    @app.middleware("http")
    async def tenant_context(request, call_next):
        token = current_tenant.set(request.headers["x-test-tenant"])
        try:
            return await call_next(request)
        finally:
            current_tenant.reset(token)
    app.include_router(edo_routes.edo_router)
    app.dependency_overrides[edo_routes.authorized] = lambda: SimpleNamespace(user_id="user")
    app.dependency_overrides[get_supply_db] = lambda: SourceDB()
    client = TestClient(app)
    def call(method, path, tenant, **kwargs):
        return client.request(method, path, headers={"x-test-tenant": tenant}, **kwargs)

    result = call("POST", "/edo/relationships", "FIRST", json={"participant_id": second})
    assert result.status_code == 201, result.text
    relation = result.json()["id"]
    assert call("POST", f"/edo/relationships/{relation}/decision", "FIRST", json={"decision": "accept"}).status_code == 409
    assert call("POST", f"/edo/relationships/{relation}/decision", "SECOND", json={"decision": "accept"}).status_code == 200
    result = call("POST", "/edo/documents", "FIRST", json={"participant_id":second,"document_type":"contract","document_id":1,"file_ids":["file-1"]})
    assert result.status_code == 201, result.text
    document = result.json()
    file_path.write_bytes(b"changed source")
    doc_id = document["id"]
    file_id = document["files"][0]["id"]
    assert call("GET", f"/edo/documents/{doc_id}", "THIRD").status_code == 404
    assert call("GET", f"/edo/documents/{doc_id}/files/{file_id}", "SECOND").content == b"original contract"
    assert call("POST", f"/edo/documents/{doc_id}/decision", "FIRST", json={"decision":"accept"}).status_code == 404
    assert call("POST", f"/edo/documents/{doc_id}/decision", "SECOND", json={"decision":"accept"}).json()["status"] == "accepted"
    assert call("POST", f"/edo/documents/{doc_id}/decision", "SECOND", json={"decision":"reject"}).status_code == 409
    assert call("GET", f"/edo/documents/{doc_id}", "FIRST").json()["status"] == "accepted"


def test_edo_access_is_explicit_per_site(monkeypatch):
    from fastapi import HTTPException
    from app.routes.edo_routes import authorized
    import pytest

    monkeypatch.setenv("TENANT_FIRST_EDO_USERS", "user-1,user-2")
    monkeypatch.delenv("TENANT_SECOND_EDO_USERS", raising=False)
    token = current_tenant.set("FIRST")
    try:
        assert authorized(SimpleNamespace(user_id="user-1")).user_id == "user-1"
        with pytest.raises(HTTPException) as error:
            authorized(SimpleNamespace(user_id="other"))
        assert error.value.status_code == 403
    finally:
        current_tenant.reset(token)
    token = current_tenant.set("SECOND")
    try:
        with pytest.raises(HTTPException) as error:
            authorized(SimpleNamespace(user_id="user-1"))
        assert error.value.status_code == 403
    finally:
        current_tenant.reset(token)


def test_edo_wildcard_allows_authenticated_users(monkeypatch):
    from app.routes.edo_routes import authorized
    monkeypatch.setenv("TENANT_FIRST_EDO_USERS", "*")
    token = current_tenant.set("FIRST")
    try:
        assert authorized(SimpleNamespace(user_id="any-user")).user_id == "any-user"
    finally:
        current_tenant.reset(token)
