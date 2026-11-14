from sqlalchemy.orm import Session

from app.models.receipt_contract import ReceiptContract


class ReceiptContractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, receipt_id: int) -> ReceiptContract | None:
        return self.db.query(ReceiptContract).filter(ReceiptContract.id == receipt_id).first()

    def get_by_contract_id(self, contract_id: int) -> list[ReceiptContract]:
        return (
            self.db.query(ReceiptContract)
            .filter(ReceiptContract.contract_id == contract_id)
            .order_by(ReceiptContract.date.desc(), ReceiptContract.id.desc())
            .all()
        )

    def get_by_contract_ids(self, contract_ids: list[int]) -> list[ReceiptContract]:
        if not contract_ids:
            return []
        return (
            self.db.query(ReceiptContract)
            .filter(ReceiptContract.contract_id.in_(contract_ids))
            .order_by(ReceiptContract.date.desc(), ReceiptContract.id.desc())
            .all()
        )

    def create(self, payload: dict) -> ReceiptContract:
        row = ReceiptContract(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: ReceiptContract) -> ReceiptContract:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: ReceiptContract) -> None:
        self.db.delete(row)
        self.db.commit()
