import sys
import uuid

from sqlalchemy import func

from app.database import ReferenceSessionLocal, SupplySessionLocal
from app.models.object_setting import ObjectSetting
from app.models.reference_object import RefObject

DEFAULT_USER_ID = "db59fc16-2e32-4669-8f91-7732d405a0cb"
ROLE = "view_invoice"
SEARCH_TERM = "мелитопол"


def main() -> None:
    user_id = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_USER_ID
    print(f"Target user_id: {user_id}")

    supply_db = SupplySessionLocal()
    reference_db = ReferenceSessionLocal()
    try:
        objects = (
            reference_db.query(RefObject)
            .filter(func.lower(RefObject.short_name).like(f"%{SEARCH_TERM}%"))
            .all()
        )
        print(f"Found {len(objects)} object(s) matching '{SEARCH_TERM}' in short_name")

        created = 0
        skipped = 0
        for obj in objects:
            existing = (
                supply_db.query(ObjectSetting)
                .filter(
                    ObjectSetting.object_id == obj.id,
                    ObjectSetting.user_id == user_id,
                    ObjectSetting.role == ROLE,
                )
                .first()
            )
            if existing:
                skipped += 1
                print(f"object_id={obj.id} ({obj.short_name}): setting already exists, skipping")
                continue

            row = ObjectSetting(
                id=str(uuid.uuid4()),
                object_id=obj.id,
                user_id=user_id,
                department_id=None,
                role=ROLE,
            )
            supply_db.add(row)
            created += 1
            print(f"object_id={obj.id} ({obj.short_name}): created object_setting")

        supply_db.commit()
        print(f"Done. Created: {created}, skipped (already existed): {skipped}")
    finally:
        supply_db.close()
        reference_db.close()


if __name__ == "__main__":
    sys.exit(main())
