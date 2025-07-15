from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cognee.extensions.scripts.jobs.skill_recall_job import get_jobs_by_skill_matching
from cognee.modules.users.exceptions.exceptions import PermissionDeniedError


class RecommendJobPayloadDTO(BaseModel):
    app_user_id: Optional[str] = None
    skills: Optional[list[str]] = None


def get_recall_router() -> APIRouter:
    router = APIRouter()

    @router.post("/job", response_model=list)
    async def recommend_job(payload: RecommendJobPayloadDTO):
        """recommend job"""
        try:
            results = await get_jobs_by_skill_matching(
                payload.skills,
                distance_threshold=0.5,
                top_k=12,
            )
            return [{"job_id": result[0], "score": result[1]} for result in results]
        except PermissionDeniedError:
            return []
        except Exception as error:
            return JSONResponse(status_code=409, content={"error": str(error)})

    return router
