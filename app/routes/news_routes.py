from fastapi import APIRouter, Depends, File, UploadFile, status
from fastapi.responses import FileResponse

from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.news import NewsPostCreate, NewsPostUpdate
from app.repositories.news_repository import NewsRepository
from app.services.news_service import NewsService

news_router = APIRouter(prefix="/news", tags=["News"])
news_media_router = APIRouter(prefix="/media/news", tags=["News"])


def build_service(supply_db: DbSupplySession) -> NewsService:
    return NewsService(NewsRepository(supply_db))


@news_router.get("", status_code=status.HTTP_200_OK)
def get_all(supply_db: DbSupplySession):
    return build_service(supply_db).get_all()


@news_router.get("/{post_id}", status_code=status.HTTP_200_OK)
def get_post(post_id: int, supply_db: DbSupplySession):
    return build_service(supply_db).get_by_id(post_id)


@news_router.post("", status_code=status.HTTP_201_CREATED)
def create_post(
    payload: NewsPostCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create(payload, _session.user_id)


@news_router.patch("/{post_id}", status_code=status.HTTP_200_OK)
def update_post(
    post_id: int,
    payload: NewsPostUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(post_id, payload, _session.user_id)


@news_router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_post(
    post_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(post_id)
    return None


@news_router.post("/upload", status_code=status.HTTP_201_CREATED)
def upload_file(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
    file: UploadFile = File(...),
):
    return build_service(supply_db).upload_file(file, _session.user_id)


@news_media_router.get("/{filename}", status_code=status.HTTP_200_OK)
def get_media(filename: str, supply_db: DbSupplySession):
    file_path = f"/home/webserver/models/supply/news/{filename}"
    return FileResponse(file_path)
