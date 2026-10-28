from fastapi import APIRouter

from app.api import admin, auth, catalog, claims, notifications, reports, staff


api_router = APIRouter(prefix="/api/v1")
api_router.include_router(auth.router)
api_router.include_router(auth.profile_router)
api_router.include_router(catalog.router)
api_router.include_router(claims.router)
api_router.include_router(reports.router)
api_router.include_router(notifications.router)
api_router.include_router(staff.router)
api_router.include_router(admin.router)

