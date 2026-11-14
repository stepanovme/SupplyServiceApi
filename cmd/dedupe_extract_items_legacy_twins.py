"""One-off cleanup: removes the twin rows created when an overlapping period was re-loaded
before legacy-row matching existed.

A "twin pair" = an old row (external_id IS NULL) and a newer row (external_id set) with identical
content. The OLD row is kept (links such as contract_extracts / extract_business_cards point at
it), receives the twin's external_id/bank_type/account_number, the twin's links are moved over
(or dropped if the old row already has an equivalent one) and the twin is deleted.

Everything runs in ONE transaction and is verified before COMMIT; the rows being deleted are
dumped to a JSON backup first.

Usage:  python3 -m cmd.dedupe_extract_items_legacy_twins [--dry-run] [--backup PATH]
"""
import argparse
import json
import sys
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import bindparam, text

from app.database import supply_engine

LINK_TABLES = ("contract_extracts", "extract_business_cards", "invoice_payment_extracts")

PAIRS_SQL = """
SELECT o.id AS old_id, n.id AS new_id
FROM extract_items o
JOIN extract_items n
  ON n.external_id IS NOT NULL AND o.external_id IS NULL AND n.id <> o.id
 AND o.operationDate <=> n.operationDate AND o.amount <=> n.amount AND o.direction <=> n.direction
 AND o.paymentPurpose <=> n.paymentPurpose AND o.payeeInn <=> n.payeeInn AND o.payerInn <=> n.payerInn
 AND o.payeeAccount <=> n.payeeAccount
"""


def _json_default(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    return str(value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", default="extract_items_twins_backup.json")
    args = parser.parse_args()

    with supply_engine.connect() as conn:
        tx = conn.begin()
        try:
            pairs = [(r.old_id, r.new_id) for r in conn.execute(text(PAIRS_SQL))]
            olds = [p[0] for p in pairs]
            news = [p[1] for p in pairs]
            print(f"twin pairs found: {len(pairs)}")

            if len(set(olds)) != len(olds) or len(set(news)) != len(news):
                print("ABORT: pairing is not 1:1 (a row matches several twins) - needs manual review")
                tx.rollback()
                return 1
            if not pairs:
                tx.rollback()
                return 0

            rows_before = conn.execute(text("SELECT COUNT(*) FROM extract_items")).scalar()

            # ---- backup of everything that is about to be deleted/moved
            backup = {
                "extract_items_to_delete": [
                    dict(r._mapping)
                    for r in conn.execute(text("SELECT * FROM extract_items WHERE id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": news})
                ],
                "links_on_deleted_rows": {},
                "pairs": pairs,
            }
            for tbl in LINK_TABLES:
                backup["links_on_deleted_rows"][tbl] = [
                    dict(r._mapping)
                    for r in conn.execute(text(f"SELECT * FROM {tbl} WHERE extract_id IN :ids").bindparams(bindparam("ids", expanding=True)), {"ids": news})
                ]
            with open(args.backup, "w", encoding="utf-8") as f:
                json.dump(backup, f, ensure_ascii=False, indent=2, default=_json_default)
            print(f"backup written: {args.backup}")

            moved = dropped = 0
            for old_id, new_id in pairs:
                conn.execute(
                    text(
                        "UPDATE extract_items o JOIN extract_items n ON n.id = :new_id "
                        "SET o.external_id = n.external_id, "
                        "    o.bank_type = COALESCE(o.bank_type, n.bank_type), "
                        "    o.account_number = COALESCE(o.account_number, n.account_number) "
                        "WHERE o.id = :old_id"
                    ),
                    {"old_id": old_id, "new_id": new_id},
                )
                for tbl in LINK_TABLES:
                    new_has = conn.execute(text(f"SELECT COUNT(*) FROM {tbl} WHERE extract_id = :i"), {"i": new_id}).scalar()
                    if not new_has:
                        continue
                    old_has = conn.execute(text(f"SELECT COUNT(*) FROM {tbl} WHERE extract_id = :i"), {"i": old_id}).scalar()
                    if old_has:
                        conn.execute(text(f"DELETE FROM {tbl} WHERE extract_id = :i"), {"i": new_id})
                        dropped += new_has
                    else:
                        conn.execute(text(f"UPDATE {tbl} SET extract_id = :o WHERE extract_id = :n"), {"o": old_id, "n": new_id})
                        moved += new_has
                conn.execute(text("DELETE FROM extract_items WHERE id = :i"), {"i": new_id})

            # ---- verify before committing
            rows_after = conn.execute(text("SELECT COUNT(*) FROM extract_items")).scalar()
            remaining = conn.execute(text(f"SELECT COUNT(*) FROM ({PAIRS_SQL}) t")).scalar()
            orphans = {
                tbl: conn.execute(text(f"SELECT COUNT(*) FROM {tbl} t LEFT JOIN extract_items e ON e.id = t.extract_id WHERE e.id IS NULL")).scalar()
                for tbl in LINK_TABLES
            }
            print(f"rows: {rows_before} -> {rows_after} | links moved={moved} dropped(duplicate)={dropped} | "
                  f"twins left={remaining} | orphan links={orphans}")

            ok = rows_after == rows_before - len(pairs) and remaining == 0 and not any(orphans.values())
            if not ok:
                print("VERIFICATION FAILED - rolling back")
                tx.rollback()
                return 1
            if args.dry_run:
                print("dry-run: rolling back (nothing changed)")
                tx.rollback()
                return 0
            tx.commit()
            print("COMMITTED")
            return 0
        except Exception:
            tx.rollback()
            raise


if __name__ == "__main__":
    sys.exit(main())
