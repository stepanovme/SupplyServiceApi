from fastapi import HTTPException, status

from app.models.role import (
    AssignDepartmentRole,
    AssignUserRole,
    DepartmentRole,
    Role,
    RolePermission,
    RolePermissionCreate,
    RolePermissionUpdate,
    RoleCreate,
    RoleUpdate,
    UserRole,
)
from app.repositories.department_repository import DepartmentRepository
from app.repositories.role_repository import (
    DepartmentRoleRepository,
    RolePermissionRepository,
    RoleRepository,
    UserRoleRepository,
)


class RoleService:
    def __init__(
        self,
        role_repo: RoleRepository,
        role_perm_repo: RolePermissionRepository,
        user_role_repo: UserRoleRepository,
        dept_role_repo: DepartmentRoleRepository,
        department_repo: DepartmentRepository | None = None,
    ) -> None:
        self.repo = role_repo
        self.perm_repo = role_perm_repo
        self.user_role_repo = user_role_repo
        self.dept_role_repo = dept_role_repo
        self.department_repo = department_repo

    # ── Role CRUD ────────────────────────────────────────────────

    def get_all(self, active_only: bool = True) -> list[dict]:
        rows = self.repo.get_all(active_only)
        return [self._serialize_role(r) for r in rows]

    def get_by_id(self, role_id: str) -> dict:
        role = self.repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        return self._serialize_role(role)

    def create(self, payload: RoleCreate, user_id: str) -> dict:
        existing = self.repo.get_by_name(payload.name)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Role '{payload.name}' already exists",
            )
        role = self.repo.create({"name": payload.name, "description": payload.description, "created_by": user_id})
        return self._serialize_role(role)

    def update(self, role_id: str, payload: RoleUpdate, user_id: str) -> dict:
        role = self.repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        data = payload.model_dump(exclude_unset=True)
        for key, value in data.items():
            setattr(role, key, value)
        role.updated_by = user_id
        updated = self.repo.save(role)
        return self._serialize_role(updated)

    def delete(self, role_id: str) -> None:
        role = self.repo.get_by_id(role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        self.repo.delete(role)

    # ── Permissions ──────────────────────────────────────────────

    def get_permissions(self, role_id: str) -> dict:
        return self.perm_repo.get_settings_for_role(role_id)

    def update_permissions(self, role_id: str, settings: dict, user_id: str) -> dict:
        existing = self.perm_repo.get_by_role(role_id)
        existing_map = {p.permission_key: p for p in existing}

        for permission_key, perm_settings in settings.items():
            if permission_key in existing_map:
                perm = existing_map[permission_key]
                perm.settings = perm_settings
                perm.updated_by = user_id
                self.perm_repo.save(perm)
            else:
                self.perm_repo.create({
                    "role_id": role_id,
                    "permission_key": permission_key,
                    "settings": perm_settings,
                    "created_by": user_id,
                })

        return self.perm_repo.get_settings_for_role(role_id)

    def delete_permissions(self, role_id: str) -> None:
        self.perm_repo.delete_by_role(role_id)

    # ── User role assignments ────────────────────────────────────

    def get_user_roles(self, user_id: str) -> list[dict]:
        roles = self.user_role_repo.get_roles_for_user(user_id)
        return [self._serialize_role(r) for r in roles]

    def assign_user_role(self, user_id: str, payload: AssignUserRole, actor_id: str) -> dict:
        role = self.repo.get_by_id(payload.role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        existing = self.user_role_repo.get_by_user(user_id)
        if any(ur.role_id == payload.role_id for ur in existing):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="User already has this role")
        self.user_role_repo.create({"user_id": user_id, "role_id": payload.role_id, "assigned_by": actor_id})
        return {"user_id": user_id, "role_id": payload.role_id}

    def remove_user_role(self, user_id: str, role_id: str) -> None:
        self.user_role_repo.delete_by_user_and_role(user_id, role_id)

    # ── Department role assignments ──────────────────────────────

    def get_department_roles(self, department_id: int) -> list[dict]:
        roles = self.dept_role_repo.get_roles_for_department(department_id)
        return [self._serialize_role(r) for r in roles]

    def assign_department_role(self, department_id: int, payload: AssignDepartmentRole, actor_id: str) -> dict:
        role = self.repo.get_by_id(payload.role_id)
        if not role:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Role not found")
        existing = self.dept_role_repo.get_by_department(department_id)
        if any(dr.role_id == payload.role_id for dr in existing):
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Department already has this role")
        self.dept_role_repo.create({"department_id": department_id, "role_id": payload.role_id, "assigned_by": actor_id})
        return {"department_id": department_id, "role_id": payload.role_id}

    def remove_department_role(self, department_id: int, role_id: str) -> None:
        self.dept_role_repo.delete_by_department_and_role(department_id, role_id)

    # ── Check permissions ────────────────────────────────────────

    def check_request_permission(self, user_id: str, department_ids: list[int], permission: str) -> dict:
        return self._check_permission(user_id, department_ids, "requests", permission)

    def check_object_permission(self, user_id: str, department_ids: list[int], permission: str) -> dict:
        return self._check_permission(user_id, department_ids, "objects", permission)

    def get_create_request_effective_settings(self, user_id: str, department_ids: list[int]) -> dict | None:
        all_perm_settings = []

        user_roles = self.user_role_repo.get_roles_for_user(user_id)
        for role in user_roles:
            perm = self.perm_repo.get_by_role_and_key(role.id, "requests")
            if perm and perm.settings:
                all_perm_settings.append(perm.settings)

        for dept_id in department_ids:
            dept_roles = self.dept_role_repo.get_roles_for_department(dept_id)
            for role in dept_roles:
                perm = self.perm_repo.get_by_role_and_key(role.id, "requests")
                if perm and perm.settings:
                    all_perm_settings.append(perm.settings)

        if not all_perm_settings:
            return None

        return self._merge_create_request_settings(all_perm_settings)

    def _check_permission(self, user_id: str, department_ids: list[int], permission_key: str, permission: str) -> dict:
        settings = self._get_effective_settings(user_id, department_ids, permission_key)
        if not settings:
            return {"has_access": False}
        perm = settings.get(permission)
        if perm is None:
            return {"has_access": False}
        return {"has_access": True, "setting": perm}

    def _get_effective_settings(self, user_id: str, department_ids: list[int], permission_key: str) -> dict | None:
        user_settings = self._get_user_settings(user_id, permission_key)
        if user_settings:
            return user_settings
        for dept_id in department_ids:
            dept_settings = self._get_department_settings(dept_id, permission_key)
            if dept_settings:
                return dept_settings
        return None

    def _get_user_settings(self, user_id: str, permission_key: str) -> dict | None:
        roles = self.user_role_repo.get_roles_for_user(user_id)
        for role in roles:
            perm = self.perm_repo.get_by_role_and_key(role.id, permission_key)
            if perm and perm.settings:
                return perm.settings
        return None

    def _get_department_settings(self, department_id: int, permission_key: str) -> dict | None:
        roles = self.dept_role_repo.get_roles_for_department(department_id)
        for role in roles:
            perm = self.perm_repo.get_by_role_and_key(role.id, permission_key)
            if perm and perm.settings:
                return perm.settings
        return None

    @staticmethod
    def _merge_create_request_settings(all_settings: list[dict]) -> dict:
        if not all_settings:
            return {}

        merged_create = None
        merged_except: list[str] = []
        merged_visibility = None

        for settings in all_settings:
            create_val = settings.get("create")
            create_except = settings.get("create_except_objects") or []
            visibility_val = settings.get("visibility")
            if create_val:
                if create_val == "all":
                    merged_create = "all"
                elif create_val == "all_except":
                    if merged_create != "all":
                        merged_create = "all_except"
                    merged_except.extend(create_except)
                elif create_val == "own":
                    if merged_create is None:
                        merged_create = "own"
                else:
                    if merged_create is None:
                        merged_create = create_val

            if visibility_val:
                if visibility_val == "all":
                    merged_visibility = "all"
                elif visibility_val == "own_objects":
                    if merged_visibility != "all":
                        merged_visibility = "own_objects"
                elif visibility_val == "own":
                    if merged_visibility is None:
                        merged_visibility = "own"

        merged_except = list(set(merged_except))

        return {"create": merged_create, "create_except": merged_except, "visibility": merged_visibility}

    # ── Serialize ────────────────────────────────────────────────

    @staticmethod
    def _serialize_role(role: Role) -> dict:
        return {
            "id": role.id,
            "name": role.name,
            "description": role.description,
            "is_active": role.is_active,
            "created_at": role.created_at,
            "created_by": role.created_by,
            "updated_at": role.updated_at,
            "updated_by": role.updated_by,
        }

    @staticmethod
    def _serialize_user_role(ur: UserRole) -> dict:
        return {
            "id": ur.id,
            "user_id": ur.user_id,
            "role_id": ur.role_id,
            "assigned_by": ur.assigned_by,
            "created_at": ur.created_at,
        }

    @staticmethod
    def _serialize_department_role(dr: DepartmentRole) -> dict:
        return {
            "id": dr.id,
            "department_id": dr.department_id,
            "role_id": dr.role_id,
            "assigned_by": dr.assigned_by,
            "created_at": dr.created_at,
        }