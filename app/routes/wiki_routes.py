from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.wiki import WikiPageCreate, WikiPageUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.wiki_file_repository import WikiFileRepository
from app.repositories.wiki_repository import WikiRepository
from app.services.wiki_service import WikiService

wiki_router = APIRouter(prefix="/wiki", tags=["Wiki"])
wiki_media_router = APIRouter(prefix="/media/wiki", tags=["Wiki"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
) -> WikiService:
    auth_repo = AuthUserRepository(auth_db) if auth_db else None
    return WikiService(
        WikiRepository(supply_db),
        auth_repo,
        WikiFileRepository(supply_db),
    )


@wiki_router.get("/tree", status_code=status.HTTP_200_OK)
def get_tree(
    supply_db: DbSupplySession,
):
    return build_service(supply_db).get_tree()


@wiki_router.get("/pages/{page_id}", status_code=status.HTTP_200_OK)
def get_page(
    page_id: int,
    supply_db: DbSupplySession,
):
    return build_service(supply_db).get_by_id(page_id)


@wiki_router.post("/pages", status_code=status.HTTP_201_CREATED)
def create_page(
    payload: WikiPageCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create(payload, _session.user_id)


@wiki_router.patch("/pages/{page_id}", status_code=status.HTTP_200_OK)
def update_page(
    page_id: int,
    payload: WikiPageUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(page_id, payload, _session.user_id)


@wiki_router.delete("/pages/{page_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_page(
    page_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(page_id)
    return None


@wiki_router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_file(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    file: UploadFile = File(...),
):
    return build_service(supply_db).upload_file(file, _session.user_id)


@wiki_media_router.get("/{filename}", status_code=status.HTTP_200_OK)
def get_media(
    filename: str,
    supply_db: DbSupplySession,
):
    file_path = build_service(supply_db).get_file_path(filename)
    return FileResponse(file_path)
