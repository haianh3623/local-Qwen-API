from fastapi import APIRouter
from app.api.api_v1.endpoints import grading, config, utils, rubric

api_router = APIRouter()
api_router.include_router(grading.router, prefix="/grading", tags=["grading"])
api_router.include_router(config.router, prefix="/config", tags=["config"])
api_router.include_router(utils.router, prefix="/utils", tags=["utils"])
api_router.include_router(rubric.router, prefix="/rubric", tags=["rubric"])