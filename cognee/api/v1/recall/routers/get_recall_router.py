import logging
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from cognee.extensions.tasks.match_jobs import get_match_jobs
from cognee.modules.users.exceptions.exceptions import PermissionDeniedError
from cognee.shared.logging_utils import get_logger
from cognee.api.v1.recall.schemas import RecommendJobPayloadDTO

logger = get_logger("job")


def get_recall_router() -> APIRouter:
    router = APIRouter()

    @router.post("/job", response_model=list)
    async def recommend_job(payload: RecommendJobPayloadDTO):
        """recommend job"""
        try:
            logger.info(f"recommend_job payload: {payload.model_dump()}")
            jobs = await get_match_jobs(payload)
            return jobs
        except PermissionDeniedError:
            return []
        except Exception as error:
            logging.exception(error)
            return JSONResponse(status_code=409, content={"error": str(error)})

    return router
