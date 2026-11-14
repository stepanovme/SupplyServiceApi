import base64
import json
import os
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from fastapi import HTTPException, status

from app.repositories.push_subscription_repository import PushSubscriptionRepository

try:
    from pywebpush import WebPushException, webpush

    HAS_WEBPUSH = True
except ImportError:
    HAS_WEBPUSH = False
    WebPushException = Exception

VAPID_KEYS_FILE = Path(__file__).resolve().parent.parent.parent / "vapid_keys.json"
VAPID_CLAIMS_EMAIL = os.getenv("VAPID_CLAIMS_EMAIL", "admin@supply.st29.ru")


def _load_vapid() -> object:
    private_key = os.getenv("VAPID_PRIVATE_KEY")
    if private_key:
        from py_vapid import Vapid

        v = Vapid.from_pem(private_key.encode())
        print("[PUSH] VAPID loaded from VAPID_PRIVATE_KEY env var")
        return v

    if VAPID_KEYS_FILE.exists():
        from py_vapid import Vapid

        raw = VAPID_KEYS_FILE.read_text().strip()
        if raw.startswith("{"):
            data = json.loads(raw)
            pem = data.get("private_key", "")
            v = Vapid.from_pem(pem.encode())
        else:
            v = Vapid.from_pem(raw.encode())
        print(f"[PUSH] VAPID loaded from {VAPID_KEYS_FILE}")
        return v

    from py_vapid import Vapid

    v = Vapid()
    v.generate_keys()
    VAPID_KEYS_FILE.write_bytes(v.private_pem())
    print(f"[PUSH] Generated VAPID keys, saved to {VAPID_KEYS_FILE}")
    return v


class PushService:
    def __init__(self, repo: PushSubscriptionRepository) -> None:
        self.repo = repo
        self._vapid = _load_vapid()
        pub_bytes = self._vapid.public_key.public_bytes(
            encoding=serialization.Encoding.X962,
            format=serialization.PublicFormat.UncompressedPoint,
        )
        self._vapid_public_key = base64.urlsafe_b64encode(pub_bytes).rstrip(b"=").decode()

    def get_vapid_public_key(self) -> str:
        return self._vapid_public_key

    def subscribe(
        self,
        user_id: str,
        endpoint: str,
        p256dh: str,
        auth: str,
        device_type: str = "desktop",
        user_agent: str | None = None,
    ) -> dict:
        row = self.repo.create(
            user_id=user_id,
            endpoint=endpoint,
            p256dh=p256dh,
            auth=auth,
            device_type=device_type,
            user_agent=user_agent,
        )
        return self._serialize(row)

    def unsubscribe(self, sub_id: int, user_id: str) -> None:
        row = self.repo.get_by_id(sub_id)
        if not row or row.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
        self.repo.delete(sub_id)

    def list_subscriptions(self, user_id: str) -> list[dict]:
        rows = self.repo.get_by_user_id(user_id)
        return [self._serialize(r) for r in rows]

    def toggle_subscription(self, sub_id: int, user_id: str, is_active: bool) -> dict:
        row = self.repo.get_by_id(sub_id)
        if not row or row.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subscription not found")
        updated = self.repo.update_is_active(sub_id, is_active)
        return self._serialize(updated)

    def send_notification(self, user_id: str, title: str, body: str, data: dict | None = None) -> int:
        print(f"[PUSH] send_notification user_id={user_id} title='{title}' body='{body}'")

        if not HAS_WEBPUSH:
            print("[PUSH] pywebpush not installed, skipping")
            return 0

        subs = self.repo.get_active_by_user_id(user_id)
        print(f"[PUSH] found {len(subs)} active subscriptions for user {user_id}")

        if not subs:
            return 0

        payload = json.dumps({
            "title": title,
            "body": body,
            "data": data or {},
        })

        sent = 0
        for sub in subs:
            print(f"[PUSH] sending to sub id={sub.id} device_type={sub.device_type} endpoint={sub.endpoint[:60]}...")
            try:
                webpush(
                    subscription_info={
                        "endpoint": sub.endpoint,
                        "keys": {"p256dh": sub.p256dh, "auth": sub.auth},
                    },
                    data=payload,
                    vapid_private_key=self._vapid,
                    vapid_claims={"sub": f"mailto:{VAPID_CLAIMS_EMAIL}"},
                )
                sent += 1
                print(f"[PUSH] sent successfully to sub id={sub.id}")
            except WebPushException as e:
                err_detail = str(e)
                if hasattr(e, "response") and e.response:
                    try:
                        err_detail = f"status={e.response.status_code} body={e.response.text[:200]}"
                    except Exception:
                        pass
                print(f"[PUSH] send error for sub id={sub.id}: {err_detail}")
                if hasattr(e, "response") and e.response and e.response.status_code in (410, 404):
                    print(f"[PUSH] marking sub id={sub.id} as inactive (endpoint expired)")
                    self.repo.update_is_active(sub.id, False)
            except Exception as e:
                print(f"[PUSH] unexpected error for sub id={sub.id}: {e}")
        print(f"[PUSH] sent {sent}/{len(subs)} notifications for user {user_id}")
        return sent

    @staticmethod
    def _serialize(row) -> dict:
        return {
            "id": row.id,
            "user_id": row.user_id,
            "endpoint": row.endpoint,
            "p256dh": row.p256dh,
            "auth": row.auth,
            "device_type": row.device_type,
            "user_agent": row.user_agent,
            "is_active": row.is_active,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
