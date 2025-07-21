import os
import json

import httpx

sprounix_api_host = os.getenv("SPROUNIX_API_HOST")

from cognee.shared.logging_utils import get_logger

logger = get_logger("sprounix_api")


class SprounixApi:

    @staticmethod
    async def job_extract_result_store(job_data_str, verbose=True, timeout=5):
        url = f"{sprounix_api_host}/api/console/job/extract/result/store"
        headers = {}
        if verbose:
            logger.info(f"url: {url}")
        job_data = json.loads(job_data_str)
        params = {
            "id": job_data.get("id"),
            "result": job_data
        }
        x_timeout = httpx.Timeout(timeout, read=3.0, connect=2.0)
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=params, headers=headers, timeout=x_timeout)
            response.raise_for_status()
            return response.json()
