"""Create user_company_positions in every configured supply database."""
from pathlib import Path

from sqlalchemy import inspect, text

from app.database import _engines


def main():
    sql = (Path(__file__).parent / "sql" / "user_company_positions.sql").read_text(encoding="utf-8")
    errors = []
    visited = set()
    for site, engines in _engines.items():
        engine = engines["supply"]
        target = (engine.url.host, engine.url.port, engine.url.database)
        if target in visited:
            print(f"{site}: database already processed")
            continue
        visited.add(target)
        try:
            with engine.begin() as conn:
                conn.execute(text(sql))
                columns = {column["name"] for column in inspect(conn).get_columns("user_company_positions")}
                expected = {"user_id", "company_id", "position", "created_at", "updated_at"}
                if not expected.issubset(columns):
                    raise RuntimeError("existing table has an incompatible schema")
            print(f"{site}: {engine.url.database}: OK")
        except Exception as exc:
            errors.append(site)
            print(f"{site}: migration failed ({type(exc).__name__}): {exc}")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
