from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cognee.extensions.tasks.match_jobs import get_match_jobs
from cognee.modules.users.exceptions.exceptions import PermissionDeniedError
from cognee.shared.logging_utils import get_logger


logger = get_logger("job")


class RecommendJobPayloadDTO(BaseModel):
    app_user_id: Optional[str] = None
    desired_position: Optional[dict] = None
    resume: Optional[dict] = None


def get_recall_router() -> APIRouter:
    router = APIRouter()

    @router.post("/job", response_model=list)
    async def recommend_job(payload: RecommendJobPayloadDTO):
        """recommend job"""
        try:
            logger.info(f"recommend_job payload: {payload.model_dump()}")
            jobs = await get_match_jobs(
                payload.desired_position,
                payload.resume
            )
            return jobs
        except PermissionDeniedError:
            return []
        except Exception as error:
            return JSONResponse(status_code=409, content={"error": str(error)})

    return router
