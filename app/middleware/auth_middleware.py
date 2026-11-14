from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.database import get_auth_db, tenant_cookie_name
from app.repositories.session_repository import SessionRepository


def get_session_token(request: Request) -> str | None:
    return request.cookies.get(tenant_cookie_name())


def get_session(
    session_token: str | None = Depends(get_session_token),
    db: Session = Depends(get_auth_db),
):
    if not session_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Session token missing"
        )

    session_repository = SessionRepository(db)

    session = session_repository.get_by_token(session_token)

    if not session:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session")

    return session
