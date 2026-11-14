from typing import Literal
from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import delete
from sqlalchemy.dialects.mysql import insert
from app.database import DbSupplySession
from app.middleware.auth_middleware import get_session
from app.models.ios_push_device import IOSPushDevice

router = APIRouter(prefix="/push/ios", tags=["iOS push"])


class Device(BaseModel):
    token: str = Field(min_length=64, max_length=200, pattern=r"^[a-fA-F0-9]+$")
    environment: Literal["development", "production"]


@router.put("/device")
def register_device(payload: Device, db: DbSupplySession, session=Depends(get_session)):
    stmt = insert(IOSPushDevice).values(user_id=str(session.user_id), token=payload.token.lower(), environment=payload.environment, active=True)
    db.execute(stmt.on_duplicate_key_update(user_id=stmt.inserted.user_id, environment=stmt.inserted.environment, active=True))
    db.commit()
    return {"status": "registered"}


@router.delete("/device", status_code=204)
def unregister_device(payload: Device, db: DbSupplySession, session=Depends(get_session)):
    db.execute(delete(IOSPushDevice).where(IOSPushDevice.token == payload.token.lower(), IOSPushDevice.user_id == str(session.user_id)))
    db.commit()
    return Response(status_code=204)
