from fastapi import APIRouter

from app.api.routes.health import router as health_router
from app.api.routes.architecture import router as architecture_router
from app.api.routes.mentor import router as mentor_router
from app.api.routes.repositories import router as repositories_router
from app.api.routes.insights import router as insights_router

api_router = APIRouter()
api_router.include_router(health_router, prefix="/health", tags=["health"])
api_router.include_router(repositories_router, prefix="/repositories", tags=["repositories"])
api_router.include_router(architecture_router, prefix="/repositories", tags=["architecture"])
api_router.include_router(mentor_router, prefix="/repositories", tags=["mentor"])
api_router.include_router(insights_router, prefix="/repositories", tags=["insights"])
