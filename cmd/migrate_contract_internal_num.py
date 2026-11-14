import sys
from collections import defaultdict

from sqlalchemy import extract

from app.database import ReferenceSessionLocal, SupplySessionLocal
from app.models.contract import Contract
from app.models.reference_object import CounterpartyRef


def get_internal_counterparty_ids(db) -> set[str]:
    rows = db.query(CounterpartyRef.id).filter(CounterpartyRef.is_internal == 1).all()
    return {str(row[0]) for row in rows}


def main() -> None:
    supply_db = SupplySessionLocal()
    reference_db = ReferenceSessionLocal()
    try:
        internal_ids = get_internal_counterparty_ids(reference_db)
        print(f"Internal counterparties: {len(internal_ids)}")

        contracts = (
            supply_db.query(Contract)
            .filter(Contract.internal_num.is_not(None))
            .order_by(Contract.id.asc())
            .all()
        )
        print(f"Contracts with internal_num: {len(contracts)}")

        groups: dict[tuple[str, str, int | None], list[Contract]] = defaultdict(list)
        for c in contracts:
            if c.type == "buyer" and c.contractor_id in internal_ids:
                party = c.contractor_id
            elif c.type == "provider" and c.customer_id in internal_ids:
                party = c.customer_id
            else:
                print(f"Skipping contract {c.id} type={c.type} (no internal party)")
                continue
            year = c.date.year if c.date else None
            groups[(party, c.type, year)].append(c)

        total = 0
        for (party, ctype, year), group in sorted(
            groups.items(), key=lambda kv: (kv[0][1], kv[0][0], kv[0][2] is None, kv[0][2])
        ):
            for i, c in enumerate(group, start=1):
                if c.internal_num != str(i):
                    c.internal_num = str(i)
                    supply_db.add(c)
                    total += 1
            year_label = year if year is not None else "NULL"
            print(f"party={party} type={ctype} year={year_label}: {len(group)} -> 1..{len(group)}")

        supply_db.commit()
        print(f"Updated {total} contracts")
    finally:
        supply_db.close()
        reference_db.close()


if __name__ == "__main__":
    sys.exit(main())
