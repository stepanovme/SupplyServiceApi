"""One-off: adds the standard "plans payments" and "responsible for payment" users to every
invoice that lacks them.

  planing  (plans payments)        -> 8f1d6ffd-6652-4719-a426-5b21412d7c56
  payment  (responsible for pay.)  -> 06968a8b-e24c-4099-998d-3d4c16ebc63a

Invoices that were never sent for approval (no `approval` rows in invoice_log at all) are skipped.
A role is added only where that exact user + type pair is missing; existing rows are never touched.
The rows are plain invoice_log inserts (status_name / date_response empty, like the existing ones), so
no notifications are sent.

Everything runs in ONE transaction; the ids of the inserted rows are written to a JSON file first so
the change can be undone (see --undo).

Usage:
  python3 -m cmd.add_invoice_default_roles               # dry run: only counts
  python3 -m cmd.add_invoice_default_roles --apply       # insert
  python3 -m cmd.add_invoice_default_roles --undo FILE   # delete the rows listed in a backup file
"""
import argparse
import json
import sys
import uuid
from datetime import datetime

from sqlalchemy import text

from app.database import supply_engine

ROLES = (
    ("planing", "8f1d6ffd-6652-4719-a426-5b21412d7c56"),
    ("payment", "06968a8b-e24c-4099-998d-3d4c16ebc63a"),
)

# invoices sent for approval = have at least one approval row
SENT_FOR_APPROVAL = "SELECT DISTINCT invoice_id FROM invoice_log WHERE type = 'approval'"


def missing_invoice_ids(conn, log_type: str, user_id: str) -> list[int]:
    rows = conn.execute(
        text(
            f"SELECT i.id FROM invoice i WHERE i.id IN ({SENT_FOR_APPROVAL}) "
            "AND NOT EXISTS (SELECT 1 FROM invoice_log l WHERE l.invoice_id = i.id AND l.type = :t AND l.user_id = :u) "
            "ORDER BY i.id"
        ),
        {"t": log_type, "u": user_id},
    ).fetchall()
    return [r[0] for r in rows]


def undo(path: str) -> int:
    with open(path, encoding="utf-8") as f:
        ids = [row["id"] for row in json.load(f)["inserted"]]
    with supply_engine.begin() as conn:
        removed = 0
        for log_id in ids:
            removed += conn.execute(text("DELETE FROM invoice_log WHERE id = :i"), {"i": log_id}).rowcount
    print(f"removed {removed} of {len(ids)} rows")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--undo", metavar="FILE")
    parser.add_argument("--backup", default=None)
    args = parser.parse_args()
    if args.undo:
        return undo(args.undo)

    with supply_engine.connect() as conn:
        tx = conn.begin()
        try:
            total = conn.execute(text("SELECT COUNT(*) FROM invoice")).scalar()
            sent = conn.execute(text(f"SELECT COUNT(*) FROM ({SENT_FOR_APPROVAL}) s")).scalar()
            print(f"invoices: {total} | sent for approval: {sent} | skipped (no approvers at all): {total - sent}")

            plan = {}
            for log_type, user_id in ROLES:
                ids = missing_invoice_ids(conn, log_type, user_id)
                plan[(log_type, user_id)] = ids
                print(f"  {log_type:8s} {user_id}: missing on {len(ids)} invoices")

            if not args.apply:
                print("dry run: nothing written")
                tx.rollback()
                return 0

            inserted = []
            for (log_type, user_id), ids in plan.items():
                for invoice_id in ids:
                    log_id = str(uuid.uuid4())
                    conn.execute(
                        text(
                            "INSERT INTO invoice_log (id, user_id, invoice_id, type, status_name, date_response) "
                            "VALUES (:id, :u, :inv, :t, NULL, NULL)"
                        ),
                        {"id": log_id, "u": user_id, "inv": invoice_id, "t": log_type},
                    )
                    inserted.append({"id": log_id, "invoice_id": invoice_id, "type": log_type, "user_id": user_id})

            # verification inside the transaction: nothing is missing any more, nothing outside the scope was touched
            for log_type, user_id in ROLES:
                left = len(missing_invoice_ids(conn, log_type, user_id))
                if left:
                    raise RuntimeError(f"{left} invoices still miss {log_type} after the insert")
            skipped_with_logs = conn.execute(
                text(
                    "SELECT COUNT(*) FROM invoice_log WHERE id IN :ids AND invoice_id NOT IN (" + SENT_FOR_APPROVAL + ")"
                ).bindparams(__import__("sqlalchemy").bindparam("ids", expanding=True)),
                {"ids": [r["id"] for r in inserted] or [""]},
            ).scalar()
            if skipped_with_logs:
                raise RuntimeError("rows were inserted for invoices that were never sent for approval")

            backup = args.backup or f"cmd/sql/invoice_default_roles_backup_{datetime.now():%Y-%m-%d_%H%M%S}.json"
            with open(backup, "w", encoding="utf-8") as f:
                json.dump({"inserted": inserted}, f, ensure_ascii=False, indent=1)
            tx.commit()
            print(f"COMMITTED: {len(inserted)} rows inserted; undo list: {backup}")
            return 0
        except Exception:
            tx.rollback()
            raise


if __name__ == "__main__":
    sys.exit(main())
