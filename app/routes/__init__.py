from fastapi import APIRouter

from app.routes.project_user_roles_routes import project_user_roles_router
from app.routes.projects_routes import projects_router
from app.routes.request_objects_routes import request_objects_router
from app.routes.requests_routes import requests_router

main_router = APIRouter(prefix="/api/supply")

main_router.include_router(projects_router)
main_router.include_router(project_user_roles_router)
main_router.include_router(requests_router)
main_router.include_router(request_objects_router)
