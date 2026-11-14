from sqlalchemy.orm import Session

from app.models.extract import Extract, ExtractFile, ExtractItem, ExtractItemPayment


class ExtractRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_extracts(self) -> list[Extract]:
        return self.db.query(Extract).order_by(Extract.created_at.desc()).all()

    def get_extract_by_id(self, extract_id: int) -> Extract | None:
        return self.db.query(Extract).filter(Extract.id == extract_id).first()

    def get_extract_by_id_for_user(self, extract_id: int, user_id: str) -> Extract | None:
        return (
            self.db.query(Extract)
            .filter(Extract.id == extract_id, Extract.created_by == user_id)
            .first()
        )

    def get_items_by_extract_id(self, extract_id: int) -> list[ExtractItem]:
        return self.db.query(ExtractItem).filter(ExtractItem.extract_id == extract_id).all()

    def get_item_by_id(self, item_id: str) -> ExtractItem | None:
        return self.db.query(ExtractItem).filter(ExtractItem.id == item_id).first()

    def get_files_by_extract_id(self, extract_id: int) -> list[ExtractFile]:
        return self.db.query(ExtractFile).filter(ExtractFile.extract_id == extract_id).all()

    def get_file_by_id(self, file_id: str) -> ExtractFile | None:
        return self.db.query(ExtractFile).filter(ExtractFile.id == file_id).first()

    def get_payments_by_item_id(self, item_id: str) -> list[ExtractItemPayment]:
        return self.db.query(ExtractItemPayment).filter(ExtractItemPayment.extract_item_id == item_id).all()

    def get_payment_by_id(self, payment_id: str) -> ExtractItemPayment | None:
        return self.db.query(ExtractItemPayment).filter(ExtractItemPayment.id == payment_id).first()

    def create_extract(self, payload: dict) -> Extract:
        row = Extract(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_extract(self, row: Extract) -> Extract:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_extract(self, row: Extract) -> None:
        self.db.delete(row)
        self.db.commit()

    def create_item(self, payload: dict) -> ExtractItem:
        row = ExtractItem(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_item(self, row: ExtractItem) -> ExtractItem:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_item(self, row: ExtractItem) -> None:
        self.db.delete(row)
        self.db.commit()

    def create_file(self, payload: dict) -> ExtractFile:
        row = ExtractFile(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_file(self, row: ExtractFile) -> None:
        self.db.delete(row)
        self.db.commit()

    def create_payment(self, payload: dict) -> ExtractItemPayment:
        row = ExtractItemPayment(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def save_payment(self, row: ExtractItemPayment) -> ExtractItemPayment:
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_payment_by_item_and_source(self, extract_item_id: str, source_id: str, type: str) -> ExtractItemPayment | None:
        return self.db.query(ExtractItemPayment).filter(
            ExtractItemPayment.extract_item_id == extract_item_id,
            ExtractItemPayment.source_id == source_id,
            ExtractItemPayment.type == type,
        ).first()

    def delete_payment(self, row: ExtractItemPayment) -> None:
        self.db.delete(row)
        self.db.commit()
