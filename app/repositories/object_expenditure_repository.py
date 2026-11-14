from sqlalchemy.orm import Session

from app.models.object_expenditure import ObjectExpenditure


class ObjectExpenditureRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, expenditure_id: int) -> ObjectExpenditure | None:
        return self.db.query(ObjectExpenditure).filter(ObjectExpenditure.id == expenditure_id).first()

    def get_by_object_id(self, object_id: str) -> list[ObjectExpenditure]:
        return (
            self.db.query(ObjectExpenditure)
            .filter(ObjectExpenditure.object_id == object_id)
            .order_by(ObjectExpenditure.date.desc(), ObjectExpenditure.id.desc())
            .all()
        )

    def create(self, payload: dict) -> ObjectExpenditure:
        row = ObjectExpenditure(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: ObjectExpenditure) -> ObjectExpenditure:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: ObjectExpenditure) -> None:
        self.db.delete(row)
        self.db.commit()
