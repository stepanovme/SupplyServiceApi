import binascii
import os
from pathlib import Path

import httpx
from cryptography.fernet import Fernet
from fastapi import HTTPException, status

from app.models.one_c import (
    OneCOrganizationCreate,
    OneCOrganizationUpdate,
    OneCProfileCreate,
    OneCProfileUpdate,
)
from app.repositories.one_c_repository import OneCRepository

ONE_C_KEY_FILE = os.getenv(
    "ONE_C_KEY_FILE",
    "/home/webserver/models/supply/one_c_encryption_key.key",
)


class OneCService:
    def __init__(self, repo: OneCRepository) -> None:
        self.repo = repo
        self._fernet = self.load_fernet()

    @staticmethod
    def load_fernet() -> Fernet:
        key = os.getenv("ONE_C_ENCRYPTION_KEY")
        if key:
            try:
                return Fernet(key.encode())
            except (ValueError, binascii.Error):
                pass

        key_path = Path(ONE_C_KEY_FILE)
        if key_path.exists():
            try:
                key = key_path.read_text().strip()
                return Fernet(key.encode())
            except (ValueError, binascii.Error):
                pass

        key = Fernet.generate_key().decode()
        key_path.parent.mkdir(parents=True, exist_ok=True)
        key_path.write_text(key)
        return Fernet(key.encode())

    def _encrypt(self, value: str) -> str:
        return self._fernet.encrypt(value.encode()).decode()

    def _decrypt(self, value: str) -> str:
        return self._decrypt_with_key(value)

    @staticmethod
    def _decrypt_with_key(value: str) -> str:
        fernet = OneCService.load_fernet()
        try:
            return fernet.decrypt(value.encode()).decode()
        except Exception:
            return value

    def get_profiles(self):
        profiles = self.repo.get_profiles()
        return self._serialize_profiles(profiles)

    def get_profile(self, profile_id: int):
        profile = self.repo.get_profile_by_id(profile_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C profile not found")
        return self._serialize_profile(profile)

    def create_profile(self, payload: OneCProfileCreate, user_id: str):
        data = payload.model_dump(exclude_unset=True)
        data["password"] = self._encrypt(data["password"])
        data["created_by"] = user_id
        row = self.repo.create_profile(data)
        self._sync_organizations(row)
        return self._serialize_profile(row)

    def update_profile(self, profile_id: int, payload: OneCProfileUpdate):
        row = self.repo.get_profile_by_id(profile_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C profile not found")
        data = payload.model_dump(exclude_unset=True)
        if "password" in data:
            data["password"] = self._encrypt(data["password"])
        if data:
            data["updated_at"] = __import__("datetime").datetime.now()
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_profile(row)
        return self._serialize_profile(updated)

    def delete_profile(self, profile_id: int):
        row = self.repo.get_profile_by_id(profile_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C profile not found")
        self.repo.delete_profile(row)
        return None

    def get_organizations(self, profile_id: int | None = None):
        if profile_id:
            orgs = self.repo.get_organizations_by_profile_id(profile_id)
        else:
            orgs = self.repo.get_organizations()
        profile_ids = [o.one_c_profile_id for o in orgs]
        profiles = {p.id: p for p in self.repo.get_profiles()} if orgs else {}
        return self._serialize_organizations(orgs, profiles)

    def get_organization(self, org_id: int):
        org = self.repo.get_organization_by_id(org_id)
        if not org:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C organization not found")
        profiles = {p.id: p for p in self.repo.get_profiles()}
        return self._serialize_organizations([org], profiles)[0]

    def create_organization(self, payload: OneCOrganizationCreate, user_id: str):
        profile = self.repo.get_profile_by_id(payload.one_c_profile_id)
        if not profile:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C profile not found")
        data = payload.model_dump(exclude_unset=True)
        data["created_by"] = user_id
        row = self.repo.create_organization(data)
        profiles = {p.id: p for p in self.repo.get_profiles()}
        return self._serialize_organizations([row], profiles)[0]

    def update_organization(self, org_id: int, payload: OneCOrganizationUpdate):
        row = self.repo.get_organization_by_id(org_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C organization not found")
        data = payload.model_dump(exclude_unset=True)
        if "one_c_profile_id" in data:
            profile = self.repo.get_profile_by_id(data["one_c_profile_id"])
            if not profile:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C profile not found")
        for key, value in data.items():
            setattr(row, key, value)
        updated = self.repo.save_organization(row)
        profiles = {p.id: p for p in self.repo.get_profiles()}
        return self._serialize_organizations([updated], profiles)[0]

    def delete_organization(self, org_id: int):
        row = self.repo.get_organization_by_id(org_id)
        if not row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="1C organization not found")
        self.repo.delete_organization(row)
        return None

    def _serialize_profiles(self, profiles):
        return [self._serialize_profile(p) for p in profiles]

    def _serialize_profile(self, profile):
        return {
            "id": profile.id,
            "name": profile.name,
            "username": profile.username,
            "password": self._decrypt(profile.password),
            "api_link": profile.api_link,
            "created_at": profile.created_at,
            "created_by": profile.created_by,
            "updated_at": profile.updated_at,
            "updated_by": profile.updated_by,
        }

    def _serialize_organizations(self, orgs, profiles):
        return [
            {
                "id": o.id,
                "ref_key": o.ref_key,
                "name": o.name,
                "inn": o.inn,
                "one_c_profile_id": o.one_c_profile_id,
                "profile_name": profiles.get(o.one_c_profile_id).name if profiles.get(o.one_c_profile_id) else None,
                "created_at": o.created_at,
                "created_by": o.created_by,
            }
            for o in orgs
        ]

    def _sync_organizations(self, profile):
        password = self._decrypt(profile.password)
        base_url = profile.api_link.rstrip("/")
        odata_url = f"{base_url}/odata/standard.odata"

        try:
            with httpx.Client(
                auth=(profile.username, password),
                timeout=httpx.Timeout(60.0),
            ) as client:
                resp = client.get(
                    f"{odata_url}/Catalog_Организации",
                    params={"$format": "json", "$select": "Ref_Key,Description,ИНН"},
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data.get("value", []):
                    ref_key = item.get("Ref_Key")
                    if not ref_key:
                        continue
                    name = item.get("Description", "")
                    inn = item.get("ИНН", "")

                    existing = self.repo.get_organization_by_ref_key_and_profile(ref_key, profile.id)
                    if existing:
                        if existing.name != name or existing.inn != inn:
                            existing.name = name
                            existing.inn = inn
                            self.repo.save_organization(existing)
                    else:
                        payload = {
                            "ref_key": ref_key,
                            "name": name,
                            "inn": inn,
                            "one_c_profile_id": profile.id,
                        }
                        self.repo.create_organization(payload)
        except Exception as e:
            pass
