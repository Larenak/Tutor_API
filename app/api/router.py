from fastapi import APIRouter

from app.modules.ai.router import router as ai_router
from app.modules.auth.router import router as auth_router
from app.modules.exam_prep.router import router as exam_prep_router
from app.modules.users.router import router as users_router

api_router = APIRouter(prefix="/api/v1")
api_router.include_router(ai_router)
api_router.include_router(auth_router)
api_router.include_router(exam_prep_router)
api_router.include_router(users_router)
