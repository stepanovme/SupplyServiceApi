from sqlalchemy import CHAR, Column, DateTime, Integer

from app.database import SupplyBase, msk_now


class SecretSantaParticipant(SupplyBase):
    __tablename__ = "secret_santa_participants"

    user_id = Column(CHAR(36), primary_key=True)
    created_at = Column(DateTime, nullable=False, default=msk_now)


class SecretSantaDraw(SupplyBase):
    __tablename__ = "secret_santa_draws"

    id = Column(Integer, primary_key=True, autoincrement=True)
    giver_id = Column(CHAR(36), nullable=False, unique=True)
    receiver_id = Column(CHAR(36), nullable=False, unique=True)
    drawn_at = Column(DateTime, nullable=False, default=msk_now)
