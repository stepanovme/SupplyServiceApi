from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.dialects.mysql import insert

from app.database import DbAuthSession, DbReferenceSession, DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.auth_user import AuthUser
from app.models.reference_object import CounterpartyRef
from app.models.user_company_position import UserCompanyPosition

user_company_positions_router = APIRouter(prefix="/user-company-positions", tags=["User company positions"])


class UserCompanyPositionInput(BaseModel):
    company_id: str = Field(min_length=1, max_length=36)
    position: str | None = Field(default=None, max_length=255)


class UserCompanyPositionResponse(BaseModel):
    user_id: str
    company_id: str
    company_name: str | None
    position: str | None


def get_record(user_id: str, db: DbSupplySession, reference_db: DbReferenceSession):
    row = db.get(UserCompanyPosition, user_id)
    if row is None:
        raise HTTPException(status_code=404, detail="User company position not found")
    company = reference_db.get(CounterpartyRef, row.company_id)
    return {
        "user_id": row.user_id,
        "company_id": row.company_id,
        "company_name": (company.short_name or company.full_name) if company else None,
        "position": row.position,
    }


@user_company_positions_router.get("/my", response_model=UserCompanyPositionResponse)
def get_my_company(db: DbSupplySession, reference_db: DbReferenceSession, session=Depends(get_session)):
    return get_record(str(session.user_id), db, reference_db)


@user_company_positions_router.get("/{user_id}", response_model=UserCompanyPositionResponse)
def get_user_company(user_id: str, db: DbSupplySession, reference_db: DbReferenceSession, session=Depends(get_session)):
    return get_record(user_id, db, reference_db)


@user_company_positions_router.put("/{user_id}", response_model=UserCompanyPositionResponse)
def set_user_company(
    user_id: str,
    payload: UserCompanyPositionInput,
    db: DbSupplySession,
    auth_db: DbAuthSession,
    reference_db: DbReferenceSession,
    session=Depends(get_session),
):
    if auth_db.get(AuthUser, user_id) is None:
        raise HTTPException(status_code=404, detail="User not found")
    if reference_db.get(CounterpartyRef, payload.company_id) is None:
        raise HTTPException(status_code=404, detail="Company not found")
    stmt = insert(UserCompanyPosition).values(user_id=user_id, company_id=payload.company_id, position=payload.position)
    stmt = stmt.on_duplicate_key_update(company_id=stmt.inserted.company_id, position=stmt.inserted.position)
    db.execute(stmt)
    db.commit()
    return get_record(user_id, db, reference_db)
