import asyncio
from typing import List, Optional

from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
from cognee.infrastructure.databases.vector.models.ScoredResult import ScoredResult


async def vector_search(collection_name: str,
                        query_text: Optional[str] = None,
                        query_vector: Optional[List[float]] = None,
                        top_k: int = 10,
                        distance_threshold=0.25) -> List[ScoredResult]:
    try:
        if not collection_name:
            raise ValueError("collection_name required")
        vector_engine = get_vector_engine()
        results = await vector_engine.search(
            collection_name=collection_name, query_text=query_text, query_vector=query_vector, limit=top_k
        )
        return [item for item in results if item.score < distance_threshold]
    except CollectionNotFoundError:
        return []
    except Exception as e:
        print("Failed to initialize vector engine: %s", e)
        raise RuntimeError("Initialization error") from e


async def get_job_skill_distance_results(skill_tags, top_k=500, distance_threshold=0.25):
    try:
        results = await asyncio.gather(
            *[vector_search(
                "JobSkill_name",
                query_text=skill,
                top_k=top_k,
                distance_threshold=distance_threshold
            ) for skill in skill_tags]
        )
        return [item for sublist in results for item in sublist]
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []


async def get_job_title_distance_results(job_titles, top_k=500, distance_threshold=0.4):
    try:
        results = await asyncio.gather(
            *[vector_search(
                "Job_title",
                query_text=job_title,
                top_k=top_k,
                distance_threshold=distance_threshold
            ) for job_title in job_titles]
        )
        return [item for sublist in results for item in sublist]
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []
