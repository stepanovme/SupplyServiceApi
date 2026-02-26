from sqlalchemy.orm import Session

from app.models.reference_object import ContractRef, ObjectLevel, RefObject, WorkTypeRef


class ReferenceObjectRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_levels_tree(self, level_ids: list[str]) -> dict[str, ObjectLevel]:
        pending = {level_id for level_id in level_ids if level_id}
        loaded: dict[str, ObjectLevel] = {}

        while pending:
            rows = self.db.query(ObjectLevel).filter(ObjectLevel.id.in_(list(pending))).all()
            pending = set()
            for row in rows:
                if row.id in loaded:
                    continue
                loaded[row.id] = row
                if row.parent_id and row.parent_id not in loaded:
                    pending.add(row.parent_id)

        return loaded

    def get_objects_by_ids(self, object_ids: list[str]) -> list[RefObject]:
        unique_ids = list({object_id for object_id in object_ids if object_id})
        if not unique_ids:
            return []
        return self.db.query(RefObject).filter(RefObject.id.in_(unique_ids)).all()

    def get_contracts_by_ids(self, contract_ids: list[str]) -> list[ContractRef]:
        unique_ids = list({contract_id for contract_id in contract_ids if contract_id})
        if not unique_ids:
            return []
        return self.db.query(ContractRef).filter(ContractRef.id.in_(unique_ids)).all()

    def get_work_types_by_ids(self, work_type_ids: list[str]) -> list[WorkTypeRef]:
        unique_ids = list({work_type_id for work_type_id in work_type_ids if work_type_id})
        if not unique_ids:
            return []
        return self.db.query(WorkTypeRef).filter(WorkTypeRef.id.in_(unique_ids)).all()
