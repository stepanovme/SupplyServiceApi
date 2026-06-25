from fastapi import APIRouter, Depends, Query, status

from app.database import DbAuthSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.chat import MentionUpdate
from app.models.session import SessionDB
from app.repositories.auth_user_repository import AuthUserRepository
from app.repositories.chat_repository import ChatRepository
from app.services.chat_service import ChatService

mentions_router = APIRouter(prefix="/mentions", tags=["Mentions"])


def build_service(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
) -> ChatService:
    return ChatService(
        ChatRepository(supply_db),
        AuthUserRepository(auth_db),
    )


@mentions_router.get("", status_code=status.HTTP_200_OK)
def get_mentions(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
    user_id: str | None = Query(default=None),
    chat_id: int | None = Query(default=None),
):
    target_user = user_id or str(session.user_id)
    return build_service(supply_db, auth_db).get_mentions(target_user, chat_id)


@mentions_router.get("/{mention_id}", status_code=status.HTTP_200_OK)
def get_mention(
    mention_id: int,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).get_mention(mention_id)


@mentions_router.patch("", status_code=status.HTTP_200_OK)
def batch_update_mentions(
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    session: SessionDB = Depends(get_session),
    chat_id: int = Query(...),
    user_id: str | None = Query(default=None),
    payload: MentionUpdate = None,
):
    target_user = user_id or str(session.user_id)
    return build_service(supply_db, auth_db).batch_update_mentions(chat_id, target_user, payload)


@mentions_router.patch("/{mention_id}", status_code=status.HTTP_200_OK)
def update_mention(
    mention_id: int,
    payload: MentionUpdate,
    supply_db: DbSupplySession,
    auth_db: DbAuthSession,
    _session=Depends(get_session),
):
    return build_service(supply_db, auth_db).update_mention(mention_id, payload)
