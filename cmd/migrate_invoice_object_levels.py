import sys

from app.database import ReferenceSessionLocal, SupplySessionLocal
from app.models.invoice import Invoice
from app.models.reference_object import ObjectLevel


def main() -> None:
    supply_db = SupplySessionLocal()
    reference_db = ReferenceSessionLocal()
    try:
        object_levels_ids = {
            row[0]
            for row in (
                supply_db.query(Invoice.object_levels_id)
                .filter(Invoice.object_type == "object_levels_id")
                .filter(Invoice.object_levels_id.is_not(None))
                .distinct()
                .all()
            )
        }
        print(f"Distinct object_levels_id to process: {len(object_levels_ids)}")

        levels = (
            reference_db.query(ObjectLevel)
            .filter(ObjectLevel.id.in_(object_levels_ids))
            .all()
            if object_levels_ids
            else []
        )
        object_id_by_level_id = {level.id: level.object_id for level in levels}
        print(f"Found matching object_levels rows: {len(object_id_by_level_id)}")

        updated_rows = 0
        resolved_groups = 0
        unresolved_groups = 0

        for level_id in object_levels_ids:
            invoices = (
                supply_db.query(Invoice)
                .filter(Invoice.object_type == "object_levels_id", Invoice.object_levels_id == level_id)
                .all()
            )

            object_id = object_id_by_level_id.get(level_id)
            if object_id:
                resolved_groups += 1
                for invoice in invoices:
                    invoice.object_levels_id = object_id
                    invoice.object_type = "object"
                    supply_db.add(invoice)
                    updated_rows += 1
                print(f"object_levels_id={level_id} -> object_id={object_id}: {len(invoices)} invoice(s)")
            else:
                unresolved_groups += 1
                for invoice in invoices:
                    invoice.object_type = "object"
                    supply_db.add(invoice)
                    updated_rows += 1
                print(f"object_levels_id={level_id} -> NOT FOUND in object_levels: {len(invoices)} invoice(s), object_type set to 'object'")

        supply_db.commit()
        print(
            f"Done. Groups resolved: {resolved_groups}, unresolved: {unresolved_groups}, "
            f"invoice rows updated: {updated_rows}"
        )
    finally:
        supply_db.close()
        reference_db.close()


if __name__ == "__main__":
    sys.exit(main())
