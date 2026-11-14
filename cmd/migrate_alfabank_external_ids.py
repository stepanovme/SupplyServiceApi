"""One-off: rewrites external_id of already-loaded Alfa-Bank rows to the new key format.

The old key was "<account>:<document number>". The bank reuses document numbers across months
and between unrelated operations, so loading a statement silently dropped real operations as
"duplicates". The new key (see build_alfabank_external_id) also contains date, direction,
amount and a hash of the purpose, plus an occurrence counter for fully identical rows.

It is rebuilt purely from stored columns (the document number is taken from the old key), so no
file is needed. Run it BEFORE re-uploading statements with the new parser, otherwise every row
would be inserted a second time under its new key.

Everything runs in one transaction and is verified before COMMIT; the old->new mapping is written
to a JSON backup first.

Usage:
  python3 -m cmd.migrate_alfabank_external_ids [--dry-run] [--backup PATH] [--verify-file STATEMENT.xlsx]
"""
import argparse
import json
import sys
from collections import Counter

from sqlalchemy import text

from app.database import supply_engine
from app.services.excel_statement_parser import build_alfabank_external_id, parse_bank_excel

OLD_FORMAT_SQL = "bank_type = 'alfabank' AND external_id REGEXP '^[0-9]+:[^:#]+$'"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--backup", default="alfabank_external_ids_backup.json")
    parser.add_argument("--verify-file", help="Alfa-Bank statement .xlsx: report how many of its rows would be NEW after migration")
    args = parser.parse_args()

    with supply_engine.connect() as conn:
        tx = conn.begin()
        try:
            rows = conn.execute(
                text(
                    "SELECT id, external_id, account_number, operationDate, direction, amount, paymentPurpose "
                    f"FROM extract_items WHERE {OLD_FORMAT_SQL} ORDER BY created_at, id"
                )
            ).fetchall()
            print(f"rows in the old format: {len(rows)}")
            if not rows:
                tx.rollback()
                return 0

            seen: Counter = Counter()
            mapping: list[tuple[str, str, str]] = []  # (row id, old key, new key)
            for r in rows:
                account, _, doc = r.external_id.partition(":")
                base = build_alfabank_external_id(
                    r.account_number or account, doc, r.operationDate, r.direction, float(r.amount), r.paymentPurpose, 0
                )
                base = base[: base.rindex("#")]
                seen[base] += 1
                new_key = f"{base}#{seen[base]}"
                mapping.append((r.id, r.external_id, new_key))

            new_keys = [m[2] for m in mapping]
            if len(set(new_keys)) != len(new_keys):
                print("ABORT: new keys are not unique")
                tx.rollback()
                return 1

            with open(args.backup, "w", encoding="utf-8") as f:
                json.dump([{"id": i, "old": o, "new": n} for i, o, n in mapping], f, ensure_ascii=False, indent=1)
            print(f"backup written: {args.backup}")

            for row_id, _old, new_key in mapping:
                conn.execute(text("UPDATE extract_items SET external_id = :n WHERE id = :i"), {"n": new_key, "i": row_id})

            leftover = conn.execute(text(f"SELECT COUNT(*) FROM extract_items WHERE {OLD_FORMAT_SQL}")).scalar()
            alfa_total = conn.execute(text("SELECT COUNT(*) FROM extract_items WHERE bank_type = 'alfabank'")).scalar()
            distinct = conn.execute(text("SELECT COUNT(DISTINCT external_id) FROM extract_items WHERE bank_type = 'alfabank'")).scalar()
            print(f"after: alfabank rows={alfa_total}, distinct external_id={distinct}, still old format={leftover}")
            ok = leftover == 0 and alfa_total == distinct

            if args.verify_file:
                with open(args.verify_file, "rb") as f:
                    file_rows, _ = parse_bank_excel("alfabank", f.read())
                file_keys = {r["external_id"] for r in file_rows}
                db_keys = {r[0] for r in conn.execute(text("SELECT external_id FROM extract_items WHERE bank_type = 'alfabank'"))}
                print(f"verify against file: file rows={len(file_rows)} | already in DB={len(file_keys & db_keys)} | "
                      f"would be NEW on re-upload={len(file_keys - db_keys)} | DB rows not in this file={len(db_keys - file_keys)}")

            if not ok:
                print("VERIFICATION FAILED - rolling back")
                tx.rollback()
                return 1
            if args.dry_run:
                print("dry-run: rolled back, nothing changed")
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
