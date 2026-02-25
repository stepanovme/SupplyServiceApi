from fastapi import APIRouter

from app.routes.project_user_roles_routes import project_user_roles_router
from app.routes.projects_routes import projects_router

main_router = APIRouter(prefix="/api/supply")

main_router.include_router(projects_router)
main_router.include_router(project_user_roles_router)
