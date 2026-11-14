from datetime import datetime

from sqlalchemy.orm import Session

from app.models.contract_extract import ContractExtract
from app.models.extract_item import ExtractItem


class ContractExtractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_id(self, item_id: str) -> ContractExtract | None:
        return self.db.query(ContractExtract).filter(ContractExtract.id == item_id).first()

    def get_by_extract_id(self, extract_id: str) -> ContractExtract | None:
        return self.db.query(ContractExtract).filter(ContractExtract.extract_id == extract_id).first()

    def get_by_extract_ids(self, extract_ids: list[str]) -> list[ContractExtract]:
        if not extract_ids:
            return []
        return self.db.query(ContractExtract).filter(ContractExtract.extract_id.in_(extract_ids)).all()

    def get_by_contract_ids(self, contract_ids: list[int]) -> list[ContractExtract]:
        if not contract_ids:
            return []
        return self.db.query(ContractExtract).filter(ContractExtract.contract_id.in_(contract_ids)).all()

    def get_list(
        self,
        contract_id: int | None = None,
        extract_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[ContractExtract]:
        q = self.db.query(ContractExtract)
        if contract_id is not None:
            q = q.filter(ContractExtract.contract_id == contract_id)
        if extract_id is not None:
            q = q.filter(ContractExtract.extract_id == extract_id)
        return q.offset(offset).limit(limit).all()

    def create(self, row: ContractExtract) -> ContractExtract:
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save(self, row: ContractExtract) -> ContractExtract:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete(self, row: ContractExtract) -> None:
        self.db.delete(row)
        self.db.commit()

    def get_unmatched_extract_items(
        self,
        limit: int = 50,
        date_from: datetime | None = None,
        date_to: datetime | None = None,
    ) -> list[ExtractItem]:
        linked_ids = self.db.query(ContractExtract.extract_id).subquery()
        q = (
            self.db.query(ExtractItem)
            .filter(ExtractItem.id.notin_(self.db.query(linked_ids.c.extract_id)))
            .filter(ExtractItem.paymentPurpose.is_not(None))
        )
        if date_from is not None:
            q = q.filter(ExtractItem.operationDate >= date_from)
        if date_to is not None:
            q = q.filter(ExtractItem.operationDate <= date_to)
        return q.order_by(ExtractItem.operationDate.desc()).limit(limit).all()
