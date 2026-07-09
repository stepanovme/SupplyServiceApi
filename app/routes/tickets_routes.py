from fastapi import APIRouter, Depends, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.ticket import TicketCreate, TicketUpdate, TicketUserCreate, TicketUserUpdate
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.ticket_repository import TicketRepository
from app.services.ticket_service import TicketService

tickets_router = APIRouter(prefix="/tickets", tags=["Tickets"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession | None = None,
) -> TicketService:
    auth_repo = AuthUserRepository(auth_db) if auth_db else None
    return TicketService(TicketRepository(supply_db), auth_repo)


# --- Ticket ---

@tickets_router.get("", status_code=status.HTTP_200_OK)
def get_all(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_all()


@tickets_router.get("/my", status_code=status.HTTP_200_OK)
def get_my(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_my(_session.user_id)


@tickets_router.get("/incomplete-count", status_code=status.HTTP_200_OK)
def get_incomplete_count(
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return {"count": build_service(supply_db).get_incomplete_count(_session.user_id)}


@tickets_router.get("/{ticket_id}", status_code=status.HTTP_200_OK)
def get_by_id(
    ticket_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_by_id(ticket_id)


@tickets_router.post("", status_code=status.HTTP_201_CREATED)
def create(
    payload: TicketCreate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).create(payload, _session.user_id)


@tickets_router.patch("/{ticket_id}", status_code=status.HTTP_200_OK)
def update(
    ticket_id: int,
    payload: TicketUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update(ticket_id, payload)


@tickets_router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete(
    ticket_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete(ticket_id)
    return None


# --- TicketUser ---

@tickets_router.get("/{ticket_id}/users", status_code=status.HTTP_200_OK)
def get_users(
    ticket_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_users_by_ticket(ticket_id)


@tickets_router.post("/{ticket_id}/users", status_code=status.HTTP_201_CREATED)
def create_user(
    ticket_id: int,
    payload: TicketUserCreate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).create_user(payload, _session.user_id)


@tickets_router.patch("/users/{user_rel_id}", status_code=status.HTTP_200_OK)
def update_user(
    user_rel_id: int,
    payload: TicketUserUpdate,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    return build_service(supply_db).update_user(user_rel_id, payload)


@tickets_router.delete("/users/{user_rel_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_rel_id: int,
    supply_db: DbSupplySession,
    _session=Depends(get_session),
):
    build_service(supply_db).delete_user(user_rel_id)
    return None
