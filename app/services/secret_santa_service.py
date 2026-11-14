import random

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.secret_santa import SecretSantaDraw, SecretSantaParticipant
from app.repositories.auth_user_repository import AuthUserRepository


class SecretSantaService:
    """Тайный Санта: каждый участник сам «крутит рулетку» и узнаёт, кому дарит. Результаты чужих розыгрышей не раскрываются."""

    def __init__(self, db: Session, auth_user_repo: AuthUserRepository) -> None:
        self.db = db
        self.auth_user_repo = auth_user_repo
        self._random = random.SystemRandom()

    def list_participants(self, me: str) -> dict:
        ids = [p.user_id for p in self.db.query(SecretSantaParticipant).all()]
        gave = {d.giver_id for d in self.db.query(SecretSantaDraw).all()}
        people = self._people(ids)
        items = sorted(({**people[i], "has_drawn": i in gave, "is_me": i == me} for i in ids), key=lambda p: p["full_name"])
        return {"total": len(ids), "drawn": len(gave), "remaining": len(ids) - len(gave), "is_participant": me in ids, "participants": items}

    def get_my_result(self, me: str) -> dict:
        participant = self.db.get(SecretSantaParticipant, me)
        draw = self.db.query(SecretSantaDraw).filter_by(giver_id=me).first()
        return {
            "is_participant": participant is not None, "has_drawn": draw is not None,
            "recipient": self._people([draw.receiver_id])[draw.receiver_id] if draw else None,
            "drawn_at": draw.drawn_at if draw else None,
        }

    def draw(self, me: str) -> dict:
        # блокируем всех участников: розыгрыши идут строго по очереди
        participants = [p.user_id for p in self.db.query(SecretSantaParticipant).with_for_update().all()]
        if me not in participants:
            self.db.rollback()
            raise HTTPException(status_code=403, detail="Вы не участвуете в тайном Санте")
        existing = self.db.query(SecretSantaDraw).filter_by(giver_id=me).first()
        if existing:
            self.db.rollback()
            return {**self.get_my_result(me), "already_drawn": True}
        draws = self.db.query(SecretSantaDraw).all()
        givers_left = set(participants) - {d.giver_id for d in draws} - {me}
        receivers_left = set(participants) - {d.receiver_id for d in draws}
        options = [r for r in receivers_left if r != me]
        # нельзя оставить последнего дарителя с единственным получателем - им самим
        options = [r for r in options if not (len(givers_left) == 1 and givers_left == receivers_left - {r})]
        if not options:
            self.db.rollback()
            raise HTTPException(status_code=409, detail="Свободных получателей не осталось")
        receiver = self._random.choice(sorted(options))
        self.db.add(SecretSantaDraw(giver_id=me, receiver_id=receiver))
        self.db.commit()
        return {**self.get_my_result(me), "already_drawn": False}

    def _people(self, ids: list[str]) -> dict[str, dict]:
        users = {u.id: u for u in self.auth_user_repo.get_by_ids(list(ids))} if ids else {}
        out = {}
        for i in ids:
            u = users.get(i)
            full = " ".join(x for x in (getattr(u, "surname", None), getattr(u, "name", None), getattr(u, "patronymic", None)) if x) if u else ""
            out[i] = {"user_id": i, "full_name": full or i, "surname": getattr(u, "surname", None), "name": getattr(u, "name", None)}
        return out
