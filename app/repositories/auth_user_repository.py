from sqlalchemy.orm import Session

from app.models.auth_user import AuthUser


class AuthUserRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_ids(self, user_ids: list[str]) -> list[AuthUser]:
        if not user_ids:
            return []
        return self.db.query(AuthUser).filter(AuthUser.id.in_(user_ids)).all()
