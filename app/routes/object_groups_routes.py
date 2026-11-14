from fastapi import APIRouter, Depends, status

from app.database import DbReferenceSession
from app.middleware.auth_middleware import get_session
from app.models.object_group import ObjectGroupAddObjects, ObjectGroupCreate, ObjectGroupUpdate
from app.repositories.object_group_repository import ObjectGroupRepository
from app.repositories.reference_object_repository import ReferenceObjectRepository
from app.services.object_group_service import ObjectGroupService

object_groups_router = APIRouter(prefix="/object-groups", tags=["ObjectGroups"])


def build_service(reference_db: DbReferenceSession) -> ObjectGroupService:
    return ObjectGroupService(ObjectGroupRepository(reference_db), ReferenceObjectRepository(reference_db))


@object_groups_router.get("", summary="Список групп объектов")
def get_groups(reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(reference_db).get_list()


# literal path must come before /{group_id}
@object_groups_router.get(
    "/by-object/{object_id}",
    summary="Группа, в которую входит объект (главный или вложенный); null, если объект вне групп",
)
def get_group_by_object(
    object_id: str, reference_db: DbReferenceSession, _session=Depends(get_session)
):
    return build_service(reference_db).get_by_object(object_id)


@object_groups_router.get("/{group_id}", summary="Получить группу объектов")
def get_group(group_id: str, reference_db: DbReferenceSession, _session=Depends(get_session)):
    return build_service(reference_db).get_by_id(group_id)


@object_groups_router.post("", status_code=status.HTTP_201_CREATED, summary="Создать группу: главный объект + объекты")
def create_group(
    payload: ObjectGroupCreate,
    
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(reference_db).create(payload, _session.user_id)


@object_groups_router.patch("/{group_id}", summary="Изменить название/комментарий/главный объект группы")
def update_group(
    group_id: str,
    payload: ObjectGroupUpdate,
    
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(reference_db).update(group_id, payload)


@object_groups_router.delete("/{group_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Удалить группу (объекты остаются)")
def delete_group(group_id: str, reference_db: DbReferenceSession, _session=Depends(get_session)):
    build_service(reference_db).delete(group_id)
    return None


@object_groups_router.post("/{group_id}/objects", summary="Добавить объекты в группу")
def add_group_objects(
    group_id: str,
    payload: ObjectGroupAddObjects,
    
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(reference_db).add_objects(group_id, payload, _session.user_id)


@object_groups_router.delete("/{group_id}/objects/{object_id}", summary="Убрать объект из группы")
def remove_group_object(
    group_id: str,
    object_id: str,
    
    reference_db: DbReferenceSession,
    _session=Depends(get_session),
):
    return build_service(reference_db).remove_object(group_id, object_id)
