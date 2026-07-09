from sqlalchemy.orm import Session

from app.models.ticket import Ticket, TicketUser


class TicketRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # --- Ticket ---

    def get_all(self) -> list[Ticket]:
        return self.db.query(Ticket).order_by(Ticket.created_at.desc()).all()

    def get_by_user(self, user_id: str) -> list[Ticket]:
        from sqlalchemy import union
        created_q = self.db.query(Ticket.id).filter(Ticket.created_by == user_id)
        member_q = self.db.query(TicketUser.ticket_id).filter(TicketUser.user_id == user_id)
        union_q = union(created_q, member_q).subquery()
        return (
            self.db.query(Ticket)
            .filter(Ticket.id.in_(union_q))
            .order_by(Ticket.created_at.desc())
            .all()
        )

    def count_incomplete_assignee(self, user_id: str) -> int:
        completed_status = "1ff32c4b-1312-11f1-aa8c-bc241127d0bd"
        ticket_ids = self.db.query(TicketUser.ticket_id).filter(
            TicketUser.user_id == user_id,
            TicketUser.role_id == "assignee",
        ).all()
        my_ids = list({row[0] for row in ticket_ids})
        if not my_ids:
            return 0
        return self.db.query(Ticket.id).filter(
            Ticket.id.in_(my_ids),
            Ticket.status_id != completed_status,
        ).count()

    def get_by_id(self, ticket_id: int) -> Ticket | None:
        return self.db.query(Ticket).filter(Ticket.id == ticket_id).first()

    def create(self, payload: dict) -> Ticket:
        row = Ticket(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: Ticket) -> Ticket:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: Ticket) -> None:
        self.db.delete(row)
        self.db.commit()

    # --- TicketUser ---

    def get_users_by_ticket(self, ticket_id: int) -> list[TicketUser]:
        return self.db.query(TicketUser).filter(
            TicketUser.ticket_id == ticket_id
        ).order_by(TicketUser.id.desc()).all()

    def get_user_by_id(self, user_rel_id: int) -> TicketUser | None:
        return self.db.query(TicketUser).filter(TicketUser.id == user_rel_id).first()

    def create_user(self, payload: dict) -> TicketUser:
        row = TicketUser(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_user(self, row: TicketUser) -> TicketUser:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_user(self, row: TicketUser) -> None:
        self.db.delete(row)
        self.db.commit()
