"""Участники тайного Санты: python cmd/secret_santa_participants.py add <user_id> [<user_id> ...] | remove <user_id> [...] | list"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import SupplySessionLocal  # noqa: E402
from app.models.secret_santa import SecretSantaDraw, SecretSantaParticipant  # noqa: E402


def main() -> None:
    action, ids = (sys.argv[1] if len(sys.argv) > 1 else "list"), sys.argv[2:]
    db = SupplySessionLocal()
    try:
        if action == "add":
            for user_id in ids:
                if not db.get(SecretSantaParticipant, user_id):
                    db.add(SecretSantaParticipant(user_id=user_id))
            db.commit()
        if action == "remove":
            busy = db.query(SecretSantaDraw).filter(
                (SecretSantaDraw.giver_id.in_(ids)) | (SecretSantaDraw.receiver_id.in_(ids))
            ).count()
            if busy:
                sys.exit("Участник уже в паре розыгрыша: удаление сломает пары")
            for user_id in ids:
                db.query(SecretSantaParticipant).filter_by(user_id=user_id).delete()
            db.commit()
        print(f"Участников: {db.query(SecretSantaParticipant).count()}, розыгрышей: {db.query(SecretSantaDraw).count()}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
