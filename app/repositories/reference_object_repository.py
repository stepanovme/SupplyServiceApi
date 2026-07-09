from sqlalchemy.orm import Session

from app.models.reference_object import (
    BankAccount,
    ContractRef,
    CounterpartyRef,
    DetailsIP,
    DetailsLLC,
    Employee,
    ObjectLevel,
    Person,
    RefObject,
    WorkTypeRef,
)


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

    def get_level_ids_by_type(self, level_type: str) -> list[str]:
        rows = self.db.query(ObjectLevel.id).filter(ObjectLevel.level_type == level_type).all()
        return [row[0] for row in rows]

    def get_counterparty_names(self, counterparty_ids: list[str]) -> dict[str, str]:
        unique_ids = list({counterparty_id for counterparty_id in counterparty_ids if counterparty_id})
        if not unique_ids:
            return {}

        rows = (
            self.db.query(CounterpartyRef)
            .filter(CounterpartyRef.id.in_(unique_ids))
            .all()
        )

        result = {}
        for row in rows:
            name = row.short_name or row.full_name
            result[str(row.id)] = name
        return result

    def is_counterparty_internal(self, counterparty_id: str) -> bool:
        row = self.db.query(CounterpartyRef.is_internal).filter(CounterpartyRef.id == counterparty_id).first()
        return row is not None and row.is_internal == 1

    def get_counterparty_type(self, counterparty_id: str) -> str | None:
        row = self.db.query(CounterpartyRef.type).filter(CounterpartyRef.id == counterparty_id).first()
        return row[0] if row else None

    def get_details_llc(self, counterparty_id: str) -> DetailsLLC | None:
        return self.db.query(DetailsLLC).filter(DetailsLLC.counterparties_id == counterparty_id).first()

    def get_details_ip(self, counterparty_id: str) -> DetailsIP | None:
        return self.db.query(DetailsIP).filter(DetailsIP.counterparty_id == counterparty_id).first()

    def get_person(self, person_id: str) -> Person | None:
        return self.db.query(Person).filter(Person.id == person_id).first()

    def get_employee(self, person_id: str, counterparty_id: str) -> Employee | None:
        return self.db.query(Employee).filter(
            Employee.person_id == person_id,
            Employee.counterparty_id == counterparty_id,
        ).first()

    def get_bank_accounts(self, counterparty_id: str) -> list[BankAccount]:
        return self.db.query(BankAccount).filter(BankAccount.counterparty_id == counterparty_id).all()

    def resolve_object_name(self, object_level_id: str) -> str | None:
        level = self.db.query(ObjectLevel).filter(ObjectLevel.id == object_level_id).first()
        if not level:
            return None
        parts = []
        current = level
        work_type_name = None
        agreement_name = None
        section_name = None

        while current:
            if current.level_type == "worktype" and current.work_type:
                wt = self.db.query(WorkTypeRef).filter(WorkTypeRef.id == current.work_type).first()
                if wt:
                    work_type_name = wt.name
            elif current.level_type == "agreement":
                if current.contract_id:
                    cr = self.db.query(ContractRef).filter(ContractRef.id == current.contract_id).first()
                    if cr:
                        agreement_name = cr.name
                if current.name:
                    agreement_name = current.name
            elif current.level_type == "section":
                if current.name:
                    section_name = current.name
            if current.parent_id:
                current = self.db.query(ObjectLevel).filter(ObjectLevel.id == current.parent_id).first()
            else:
                current = None

        obj = self.db.query(RefObject).filter(RefObject.id == level.object_id).first()
        object_name = obj.short_name if obj else level.object_id

        parts = [p for p in [object_name, section_name, agreement_name, work_type_name] if p]
        return " - ".join(parts) if parts else None
