from fastapi import APIRouter, Depends

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.repositories.auth_user_repository import AuthUserRepository
from app.services.secret_santa_service import SecretSantaService

secret_santa_router = APIRouter(prefix="/secret-santa", tags=["Secret Santa"])


def build_service(supply_db, auth_db) -> SecretSantaService:
    return SecretSantaService(supply_db, AuthUserRepository(auth_db))


@secret_santa_router.get("/participants", summary="Участники (для колеса рулетки) и кто уже крутил")
def list_participants(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).list_participants(str(_session.user_id))


@secret_santa_router.get("/me", summary="Кому я дарю подарок (только мой результат)")
def get_my_result(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).get_my_result(str(_session.user_id))


@secret_santa_router.post("/draw", summary="Крутить рулетку: выпадает получатель подарка (повторно не перекручивается)")
def draw(supply_db: DbSupplySession, auth_db: DbAuthSession, _session=Depends(get_session)):
    return build_service(supply_db, auth_db).draw(str(_session.user_id))
