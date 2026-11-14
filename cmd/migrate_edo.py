"""Install the shared EDO hub and assign stable IDs to configured sites."""
import os
import uuid
from sqlalchemy import inspect, select
from sqlalchemy.orm import Session
from app.database import _engines
from app.models.edo_exchange import EdoBase, EdoParticipant


def main():
    name = os.getenv("EDO_HUB_TENANT")
    if not name or name not in _engines:
        raise SystemExit("Set EDO_HUB_TENANT to a configured site")
    engine = _engines[name]["supply"]
    EdoBase.metadata.create_all(engine)
    with Session(engine) as db, db.begin():
        for site in _engines:
            row = db.scalar(select(EdoParticipant).where(EdoParticipant.tenant == site))
            if row is None:
                row = EdoParticipant(id=str(uuid.uuid4()), tenant=site)
                db.add(row)
                db.flush()
            print(f"{site}: {row.id}")
    inspector = inspect(engine)
    for table in EdoBase.metadata.tables:
        if not inspector.has_table(table):
            raise RuntimeError(f"Missing table: {table}")
    print(f"EDO hub ready in {name} ({engine.url.database})")


if __name__ == "__main__":
    main()
