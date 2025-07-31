import asyncio
from typing import List, Optional

from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.infrastructure.databases.vector.embeddings import get_embedding_engine
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
from cognee.infrastructure.databases.vector.models.ScoredResult import ScoredResult
from cognee.shared.logging_utils import get_logger

logger = get_logger("job")


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
        logger.error(f"Failed to initialize vector engine: {str(e)}")
        raise RuntimeError("Initialization error") from e


async def get_job_skill_distance_results(skill_tags, top_k=500, distance_threshold=0.25):
    try:
        embedding_engine = get_embedding_engine()
        skill_tag_embeddings = await embedding_engine.embed_text(skill_tags)

        results = await asyncio.gather(
            *[vector_search(
                "JobSkill_name",
                query_vector=skill_vector,
                top_k=top_k,
                distance_threshold=distance_threshold
            ) for skill_vector in skill_tag_embeddings]
        )
        return [item for sublist in results for item in sublist]
    except Exception as e:
        logger.error(f"Error during vector search: {e}")
        return []


async def get_job_title_distance_results(texts, top_k=500, distance_threshold=0.4):
    try:
        embedding_engine = get_embedding_engine()
        embeddings = await embedding_engine.embed_text(texts)

        results = await asyncio.gather(
            *[vector_search(
                "Job_title",
                query_vector=query_vector,
                top_k=top_k,
                distance_threshold=distance_threshold
            ) for query_vector in embeddings]
        )
        return [item for sublist in results for item in sublist]
    except Exception as e:
        logger.error(f"Error during vector search: {e}")
        return []


async def get_job_function_distance_results(texts, top_k=500, distance_threshold=0.4):
    try:
        embedding_engine = get_embedding_engine()
        embeddings = await embedding_engine.embed_text(texts)

        results = await asyncio.gather(
            *[vector_search(
                "JobFunction_name",
                query_vector=query_vector,
                top_k=top_k,
                distance_threshold=distance_threshold
            ) for query_vector in embeddings]
        )
        return [item for sublist in results for item in sublist]
    except Exception as e:
        logger.error(f"Error during vector search: {e}")
        return []


async def get_responsibility_distance_results(texts, top_k=500, distance_threshold=0.6):
    try:
        embedding_engine = get_embedding_engine()
        embeddings = await embedding_engine.embed_text(texts)

        results = await asyncio.gather(
            *[vector_search(
                "ResponsibilityItem_item",
                query_vector=query_vector,
                top_k=top_k,
                distance_threshold=distance_threshold
            ) for query_vector in embeddings]
        )
        return [item for sublist in results for item in sublist]
    except Exception as e:
        logger.error(f"Error during vector search: {e}")
        return []
