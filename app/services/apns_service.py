"""Token-based APNs delivery; credentials are read only from environment/files."""
import base64
import json
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.asymmetric.utils import decode_dss_signature
from sqlalchemy import select

from app.database import SupplySessionLocal
from app.models.ios_push_device import IOSPushDevice

logger = logging.getLogger(__name__)
_executor = ThreadPoolExecutor(max_workers=4, thread_name_prefix="apns")


def _b64(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _jwt(team_id, key_id, path):
    header = _b64(json.dumps({"alg": "ES256", "kid": key_id}, separators=(",", ":")).encode())
    claims = _b64(json.dumps({"iss": team_id, "iat": int(time.time())}, separators=(",", ":")).encode())
    message = f"{header}.{claims}".encode()
    key = serialization.load_pem_private_key(Path(path).read_bytes(), password=None)
    r, s = decode_dss_signature(key.sign(message, ec.ECDSA(hashes.SHA256())))
    return f"{header}.{claims}.{_b64(r.to_bytes(32, 'big') + s.to_bytes(32, 'big'))}"


def _deliver(user_id, title, body, data):
    team, key_id, path, topic = (os.getenv(key) for key in ("APNS_TEAM_ID", "APNS_KEY_ID", "APNS_KEY_PATH", "APNS_BUNDLE_ID"))
    if not all((team, key_id, path, topic)):
        return
    db = SupplySessionLocal()
    try:
        devices = db.scalars(select(IOSPushDevice).where(IOSPushDevice.user_id == user_id, IOSPushDevice.active.is_(True))).all()
        if not devices:
            return
        jwt = _jwt(team, key_id, path)
        payload = {"aps": {"alert": {"title": (title or "Уведомление")[:120], "body": (body or "")[:200]}, "sound": "default"}, **data}
        with httpx.Client(http2=True, timeout=10) as client:
            for device in devices:
                base = "https://api.sandbox.push.apple.com" if device.environment == "development" else "https://api.push.apple.com"
                try:
                    response = client.post(f"{base}/3/device/{device.token}", headers={"authorization": f"bearer {jwt}", "apns-topic": topic, "apns-push-type": "alert", "apns-priority": "10"}, json=payload)
                    if response.status_code == 410 or (response.status_code == 400 and response.json().get("reason") in ("BadDeviceToken", "DeviceTokenNotForTopic")):
                        device.active = False
                    elif response.status_code != 200:
                        logger.warning("APNs returned %s", response.status_code)
                except (httpx.HTTPError, ValueError):
                    logger.exception("APNs delivery failed")
        db.commit()
    except Exception:
        logger.exception("APNs worker failed")
    finally:
        db.close()


def schedule_notification(user_id, title, body, data):
    if not all(os.getenv(k) for k in ("APNS_TEAM_ID", "APNS_KEY_ID", "APNS_KEY_PATH", "APNS_BUNDLE_ID")):
        return
    context = copy_context()
    _executor.submit(context.run, _deliver, str(user_id), title, body, data)
