from sqlalchemy.orm import Session

from app.models.one_c import OneCOrganization, OneCProfile


class OneCRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create_profile(self, payload: dict) -> OneCProfile:
        row = OneCProfile(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_profile_by_id(self, profile_id: int) -> OneCProfile | None:
        return self.db.query(OneCProfile).filter(OneCProfile.id == profile_id).first()

    def get_profiles(self) -> list[OneCProfile]:
        return self.db.query(OneCProfile).order_by(OneCProfile.id.desc()).all()

    def save_profile(self, row: OneCProfile) -> OneCProfile:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_profile(self, row: OneCProfile) -> None:
        self.db.delete(row)
        self.db.commit()

    def create_organization(self, payload: dict) -> OneCOrganization:
        row = OneCOrganization(**payload)
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row

    def get_organization_by_id(self, org_id: int) -> OneCOrganization | None:
        return self.db.query(OneCOrganization).filter(OneCOrganization.id == org_id).first()

    def get_organizations(self) -> list[OneCOrganization]:
        return self.db.query(OneCOrganization).order_by(OneCOrganization.name).all()

    def get_organizations_by_profile_id(self, profile_id: int) -> list[OneCOrganization]:
        return (
            self.db.query(OneCOrganization)
            .filter(OneCOrganization.one_c_profile_id == profile_id)
            .order_by(OneCOrganization.name)
            .all()
        )

    def get_organization_by_ref_key_and_profile(self, ref_key: str, profile_id: int) -> OneCOrganization | None:
        return (
            self.db.query(OneCOrganization)
            .filter(
                OneCOrganization.ref_key == ref_key,
                OneCOrganization.one_c_profile_id == profile_id,
            )
            .first()
        )

    def get_organizations_by_profile_ids(self, profile_ids: list[int]) -> dict[int, list[OneCOrganization]]:
        if not profile_ids:
            return {}
        rows = (
            self.db.query(OneCOrganization)
            .filter(OneCOrganization.one_c_profile_id.in_(profile_ids))
            .order_by(OneCOrganization.name)
            .all()
        )
        result: dict[int, list[OneCOrganization]] = {}
        for row in rows:
            result.setdefault(row.one_c_profile_id, []).append(row)
        return result

    def save_organization(self, row: OneCOrganization) -> OneCOrganization:
        self.db.commit()
        self.db.refresh(row)
        return row

    def delete_organization(self, row: OneCOrganization) -> None:
        self.db.delete(row)
        self.db.commit()
