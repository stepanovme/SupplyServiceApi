import sys

from app.database import SupplySessionLocal
from app.models.invoice import Invoice
from app.models.supply_request import SupplyRequest

# SupplyRequest.object_type uses "object" | "object_levels",
# Invoice.object_type uses "object" | "object_levels_id" - map between the two enums.
REQUEST_TO_INVOICE_OBJECT_TYPE = {
    "object": "object",
    "object_levels": "object_levels_id",
}


def main() -> None:
    supply_db = SupplySessionLocal()
    try:
        invoices = (
            supply_db.query(Invoice)
            .filter(Invoice.request_id.is_not(None))
            .all()
        )
        print(f"Invoices with request_id: {len(invoices)}")

        request_ids = {invoice.request_id for invoice in invoices}
        requests = (
            supply_db.query(SupplyRequest)
            .filter(SupplyRequest.id.in_(request_ids))
            .all()
            if request_ids
            else []
        )
        requests_by_id = {request.id: request for request in requests}
        print(f"Matching requests found: {len(requests_by_id)}")

        updated = 0
        missing_request = 0
        for invoice in invoices:
            request = requests_by_id.get(invoice.request_id)
            if not request:
                missing_request += 1
                print(f"invoice.id={invoice.id}: request_id={invoice.request_id} not found, skipping")
                continue

            mapped_object_type = REQUEST_TO_INVOICE_OBJECT_TYPE.get(request.object_type, request.object_type)

            invoice.object_levels_id = request.object_levels_id
            invoice.object_type = mapped_object_type
            supply_db.add(invoice)
            updated += 1

        supply_db.commit()
        print(f"Done. Updated: {updated}, skipped (request not found): {missing_request}")
    finally:
        supply_db.close()


if __name__ == "__main__":
    sys.exit(main())
