from typing import Optional

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cognee.extensions.cypher.job import get_jobs
from cognee.modules.users.exceptions.exceptions import PermissionDeniedError


class JobPayloadDTO(BaseModel):
    job_ids: list[str]


def get_job_router() -> APIRouter:
    router = APIRouter()

    @router.post("/list", response_model=list)
    async def get_job_list(payload: JobPayloadDTO):
        try:
            jobs = await get_jobs(
                payload.job_ids,
            )
            return jobs
        except PermissionDeniedError:
            return []
        except Exception as error:
            return JSONResponse(status_code=409, content={"error": str(error)})

    return router
