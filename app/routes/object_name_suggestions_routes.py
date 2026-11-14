from fastapi import APIRouter, Depends, Query, status

from app.database import DbReferenceSession
from app.middleware.auth_middleware import get_session
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.object_name_suggestion_service import ObjectNameSuggestionService

object_name_suggestions_router = APIRouter(prefix="/object-name-suggestions", tags=["ObjectNameSuggestions"])


@object_name_suggestions_router.get(
    "",
    status_code=status.HTTP_200_OK,
    summary="Предложить краткие названия объекта (ИИ)",
)
def suggest_object_names(
    object_id: str | None = Query(default=None),
    work_type_id: str | None = Query(default=None),
    full_name: str | None = Query(default=None),
    work_type_name: str | None = Query(default=None),
    reference_db: DbReferenceSession = None,
    _session=Depends(get_session),
):
    service = ObjectNameSuggestionService(ReferenceObjectRepository(reference_db))
    return service.suggest(object_id, work_type_id, full_name, work_type_name)
