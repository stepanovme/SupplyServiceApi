import json
import os
import urllib.request
import urllib.parse

from app.repositories.vk_repository import VkRepository
from app.services.ws_manager import ws_manager


VK_API_VERSION = "5.131"
VK_API_URL = "https://api.vk.com/method/"


class VkService:
    def __init__(self, repo: VkRepository) -> None:
        self.repo = repo
        self._api_token = os.getenv("VK_API_TOKEN", "")
        self._group_id = os.getenv("VK_GROUP_ID", "")
        self._community_address = os.getenv("VK_COMMUNITY_ADDRESS", "")

    def get_link_url(self, user_id: str) -> str:
        address = self._community_address
        return f"https://vk.me/{address}?ref={user_id}"

    def get_confirmation_code(self) -> str:
        return os.getenv("VK_CONFIRMATION_CODE", "")

    def handle_message_new(self, vk_id: str, ref: str | None) -> dict:
        existing_by_vk = self.repo.get_by_vk_id(vk_id)

        if ref:
            if existing_by_vk:
                self.repo.update_vk_id(existing_by_vk.user_id, vk_id)
            else:
                exists_by_ref = self.repo.get_by_ref(ref)
                if exists_by_ref:
                    self.repo.update_vk_id(exists_by_ref.user_id, vk_id)
                else:
                    self.repo.create(user_id=ref, vk_id=vk_id, ref=ref)

            ws_manager.send_to_user(ref, {"type": "vk_linked", "vk_id": vk_id})
            self._send_message(int(vk_id), "Уведомления успешно настроены!")
            return {"ok": True}

        if existing_by_vk:
            self._send_message(int(vk_id), "Уведомления уже настроены!")
            return {"ok": True, "already_linked": True}

        self._send_message(int(vk_id), "Для подключения уведомлений перейдите по ссылке на сайте в разделе «Подключить уведомления в ВК»")
        return {"ok": False, "error": "no ref and no existing link"}

    def send_notification(self, vk_id: str, message: str) -> bool:
        if not vk_id:
            return False
        return self._send_message(int(vk_id), message)

    def _send_message(self, vk_id: int, message: str) -> bool:
        if not self._api_token:
            print("[VK] no api token")
            return False

        params = urllib.parse.urlencode({
            "access_token": self._api_token,
            "v": VK_API_VERSION,
            "user_id": vk_id,
            "random_id": 0,
            "message": message,
        })
        url = f"{VK_API_URL}messages.send?{params}"

        try:
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                if "error" in data:
                    print(f"[VK] send_message error: {data['error']}")
                return "response" in data and data["response"] > 0
        except Exception as e:
            print(f"[VK] send_message exception: {e}")
            return False

    def toggle_notifications(self, user_id: str, enabled: bool) -> bool:
        link = self.repo.set_notifications(user_id, enabled)
        return link is not None

    def delete_link(self, user_id: str) -> None:
        self.repo.delete_by_user_id(user_id)

    def get_status(self, user_id: str) -> dict:
        link = self.repo.get_by_user_id(user_id)
        if not link:
            return {"linked": False, "vk_id": None, "notifications_enabled": False}
        return {
            "linked": True,
            "vk_id": link.vk_id,
            "notifications_enabled": link.notifications_enabled,
        }

    def save_vk_id(self, user_id: str, vk_id: str) -> bool:
        existing = self.repo.get_by_user_id(user_id)
        if existing:
            self.repo.update_vk_id(user_id, vk_id)
        else:
            self.repo.create(user_id=user_id, vk_id=vk_id)
        return True

    def get_vk_id(self, user_id: str) -> str | None:
        link = self.repo.get_by_user_id(user_id)
        if link and link.notifications_enabled:
            return link.vk_id
        return None
