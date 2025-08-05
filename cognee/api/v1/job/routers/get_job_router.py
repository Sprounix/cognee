from typing import Optional
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from cognee.extensions.cypher.job import get_jobs
from cognee.modules.users.exceptions.exceptions import PermissionDeniedError
from cognee.extensions.scripts.clean_all_data import delete_job_data


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

    @router.delete("/{job_id}", response_model=None)
    async def delete_job(job_id: UUID):
        if not job_id:
            return JSONResponse(status_code=409, content={"error": "Invalid job_id"})
        try:
            await delete_job_data(job_id)
        except Exception as error:
            return JSONResponse(status_code=409, content={"error": str(error)})

    return router
