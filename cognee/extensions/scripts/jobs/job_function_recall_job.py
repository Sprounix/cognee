import asyncio
import os
from typing import List

from cognee.infrastructure.databases.vector import get_vector_engine
from cognee.infrastructure.databases.vector.exceptions import CollectionNotFoundError
from cognee.infrastructure.databases.vector.models.ScoredResult import ScoredResult

os.environ['LITELLM_LOCAL_MODEL_COST_MAP'] = "True"  # Enable local model cost map for LiteLLM,避免去请求远程模型的价格信息


async def _search_in_collection(collection_name: str, query, top_k: int = 5) -> List[ScoredResult]:
    try:
        vector_engine = get_vector_engine()
    except Exception as e:
        print("Failed to initialize vector engine: %s", e)
        raise RuntimeError("Initialization error") from e

    try:
        return await vector_engine.search(
            collection_name=collection_name, query_text=query, limit=top_k
        )
    except CollectionNotFoundError:
        return []


async def get_canonical_items_by_vector(collections: List[str], items: List[str]) -> List[str]:
    """
    使用向量搜索获取标准化的查询参数。
    :param collections: List[str], 需要查询的集合名称
    :param items: List[str], 需要标准化的词汇
    :return: List[str], 标准化后的项目列表
    """
    if not items:
        return []

    try:
        results = []

        for query in items:
            res = await asyncio.gather(
                *[_search_in_collection(collection_name, query) for collection_name in collections]
            )
        results.append(res)
        node_distances = {collection: result for collection, result in zip(collections, results)}
    except CollectionNotFoundError:
        return []
    except Exception as error:
        print(f"Error during vector search: {error}")
        return []

    # 提取标准化项
    canonical_items = []
    for collection, result in node_distances.items():
        for item in result[0]:
            if isinstance(item, ScoredResult) and item.payload and item.score <= 1.0:
                payload = item.payload
                if payload.get("metadata") and "index_fields" in payload['metadata']:

                    field_name = payload['metadata']["index_fields"][0]
                    value = payload.get(field_name, "")
                    if value and value not in canonical_items:
                        canonical_items.append(value)
                        # just use the most similary two items
                        if len(canonical_items) > 1:
                            break

    # add the original query in case of missing the item
    for item in items:
        if item not in canonical_items:
            canonical_items.append(item)

    return canonical_items


async def get_jobs(tags: List[str], distance_threshold=0.2, top_k: int = 500) -> List[str]:
    if not tags:
        return []
    collections = ['Job_title', 'JobFunction_name']
    try:
        results = await asyncio.gather(
            *[_search_in_collection(collection_name, tag, top_k=top_k) for collection_name in collections for tag in
              tags]
        )
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []

    jobs = []
    for result in results:
        if not isinstance(result, list):
            continue
        for item in result:
            print(item)
            print(f"------" * 10)
            if not isinstance(item, ScoredResult):
                continue
            if item.score >= distance_threshold:
                continue
            jobs.append(item.id)
    print(jobs)
    return jobs


if __name__ == "__main__":
    tags = ["send Python so"]
    results = asyncio.run(
        get_jobs(tags, distance_threshold=0.5)
    )
    print(results)
