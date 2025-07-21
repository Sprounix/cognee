import asyncio
import os
from typing import List

from cognee.infrastructure.databases.graph import get_graph_engine
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


async def get_jobs_by_skill_matching(tags: List[str], distance_threshold=0.25, top_k: int = 10) -> List[tuple]:
    """
    使用简历中提取的一组技能（skill），对每一个技能进行向量相似性搜索，找到匹配的最多200个岗位，然后计算索索出来的所有这些岗位的技能匹配度，
    技能匹配度是指一个岗位的在不同技能搜索中出现的次数，与岗位技能总数之比。按照岗位技能匹配度，将最终的岗位列表进行排序，返回前 top_k 个岗位。
    :param skills: List[str], 用户简历中提取的技能列表
    :param top_k: int, 返回的最匹配岗位数量
    distance_threshold: float, 向量相似性搜索的距离阈值，默认0.2
    :return: List[tuple], 匹配的岗位及匹配值列表，返回的是岗位的 id，及对应的匹配值，按照由大到小顺序排列
    """
    if not tags:
        return []

    graph_engine = await get_graph_engine()

    collections = ['JobSkill_name']
    try:
        results = await asyncio.gather(
            *[_search_in_collection(collection_name, skill, top_k=500) for collection_name in collections for skill in
              tags]
        )
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []

    jobs = []
    skill_scores = {}
    for result in results:
        skill_ids = []
        if not isinstance(result, list):
            continue
        for item in result:
            if isinstance(item, ScoredResult) and item.payload and item.score < distance_threshold:
                payload = item.payload
                skill_id = payload.get("id")
                if not skill_id:
                    continue
                skill_ids.append(skill_id)
                # 如果 Job的一条skill跟简历的多条skill匹配，取最小距离的值
                skill_scores[skill_id] = min(skill_scores.get(skill_id, 100), item.score)
        if not skill_ids:
            continue
        # 使用技能 ID 查询岗位
        cypher = f"MATCH (Job:Job)-[r:skills]->(skill:JobSkill) WHERE skill.id IN {skill_ids} RETURN collect(DISTINCT Job.id) AS job_ids"
        try:
            job_results = await graph_engine.query(cypher)
            if job_results and isinstance(job_results, list):
                for job_ids in job_results:
                    for job_id in job_ids['job_ids']:
                        if job_id not in jobs:
                            jobs.append(job_id)
        except Exception as e:
            print("Failed to execture cypher search retrieval: %s", str(e))
            continue

    # 根据岗位的id，获取每个岗位的所有技能id
    cypher = f"MATCH(Job:Job)-[r:skills]->(skill:JobSkill) WHERE Job.id IN {jobs} RETURN collect(DISTINCT skill.id) AS skills, Job.id AS job_id"
    job_skills = {}
    try:
        job_results = await graph_engine.query(cypher)
        if job_results and isinstance(job_results, list):
            for job in job_results:
                job_id = job['job_id']
                skills = job.get('skills', [])
                if skills:
                    job_skills[job_id] = skills
    except Exception as e:
        print(f"Error during Cypher query: {e}")

    # 计算每个岗位的技能匹配度
    job_scores = {}
    for job_id, skills in job_skills.items():
        job_scores[job_id] = {}
        for skill_id in skills:
            if skill_id in skill_scores:
                job_scores[job_id][skill_id] = 1
            else:
                job_scores[job_id][skill_id] = 0

    job_matching_score = {}
    # 计算每个岗位的技能匹配度
    for job_id in job_scores:
        score = sum(job_scores[job_id].values()) / len(job_scores[job_id]) if job_scores[job_id] else 0.
        job_matching_score[job_id] = score

    print("job_matching_score: ", job_matching_score)
    # 按照技能匹配度排序
    sorted_jobs = sorted(job_matching_score.items(), key=lambda x: x[1], reverse=True)
    # 返回前 top_k 个岗位的 id及匹配度
    
    return sorted_jobs[:top_k]


async def get_jobs_by_title_similarity(title: str, distance_threshold=0.4, top_k: int = 20) -> List[str]:
    """
    使用岗位标题进行向量相似性搜索，找到匹配的最多500个岗位，然后返回前 top_k 个岗位。
    :param title: str, 岗位标题
    :param distance_threshold: float, 向量相似性搜索的距离阈值，默认0.2
    :param top_k: int, 返回的最匹配岗位数量
    :return: List[str], 匹配的岗位列表，返回的是岗位的 id
    """
    if not title:
        return []

    collections = ['Job_title']
    try:
        results = await asyncio.gather(
            *[_search_in_collection(collection_name, title, top_k=500) for collection_name in collections]
        )
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []

    jobs = []
    for result in results:
        if not isinstance(result, list):
            continue
        for item in result:
            if isinstance(item, ScoredResult) and item.score < distance_threshold:
                jobs.append(item.id)

    return jobs

async def get_jobs_by_experince_and_responsibilities_matching(experiences: list[str], distance_threshold=0.6, top_k: int = 50) -> List[tuple]:
    """
    使用候选人的一组经验，与岗位的职责进行向量相似性搜索，每条经验找到最多500条匹配的职责，然后计算岗位的职责中有多少条与候选人的经验匹配，根据匹配值由大到小排列
    并返回最匹配的top_k个岗位id，以及对应的匹配值。
    :param experiences: List[str], 候选人的经验列表
    :param distance_threshold: float, 向量相似性阈值，默认为0.3
    :param top_k: int, 返回最匹配的top_k个岗位id，默认为500
    :return: List[tuple], 最匹配的top_k个岗位id及匹配值
    """
    if not experiences:
        return []

    graph_engine = await get_graph_engine()

    collections = ['ResponsibilityItem_item']
    try:
        results = await asyncio.gather(
            *[_search_in_collection(collection_name, experience, top_k=500) for collection_name in collections for experience in
              experiences]
        )
    except Exception as e:
        print(f"Error during vector search: {e}")
        return []

    jobs = []
    responsibility_scores = {}
    for result in results:
        responsibility_ids = []
        if not isinstance(result, list):
            continue
        for item in result:
            if isinstance(item, ScoredResult) and item.payload and item.score < distance_threshold:
                payload = item.payload
                responsibility_id = payload.get("id")
                if not responsibility_id:
                    continue
                responsibility_ids.append(responsibility_id)
                # 如果 Job的一条responsibility跟简历的多条experience匹配，取最小距离值
                responsibility_scores[ responsibility_id] = min(responsibility_scores.get(responsibility_id, 100), item.score)
        if not responsibility_ids:
            continue
        # 使用技能 ID 查询岗位
        cypher = f"MATCH (Job:Job)-[r:responsibilities]->(res:ResponsibilityItem) WHERE res.id IN {responsibility_ids} RETURN collect(DISTINCT Job.id) AS job_ids"
        try:
            job_results = await graph_engine.query(cypher)
            if job_results and isinstance(job_results, list):
                for job_ids in job_results:
                    for job_id in job_ids['job_ids']:
                        if job_id not in jobs:
                            jobs.append(job_id)
        except Exception as e:
            print("Failed to execture cypher search retrieval: %s", str(e))
            continue

    # 根据岗位的id，获取每个岗位的所有responsibility_id
    cypher = f"MATCH(Job:Job)-[r:responsibilities]->(res:ResponsibilityItem) WHERE Job.id IN {jobs} RETURN collect(DISTINCT res.id) AS responsibilities, Job.id AS job_id"
    job_responsibilities = {}
    try:
        job_results = await graph_engine.query(cypher)
        if job_results and isinstance(job_results, list):
            for job in job_results:
                job_id = job['job_id']
                responsibilities = job.get('responsibilities', [])
                if responsibilities:
                    job_responsibilities[job_id] = responsibilities
    except Exception as e:
        print(f"Error during Cypher query: {e}")

    # 计算每个岗位的职责匹配度
    job_scores = {}
    for job_id, responsibilities in job_responsibilities.items():
        job_scores[job_id] = {}
        for res_id in responsibilities:
            if res_id in responsibility_scores:
                job_scores[job_id][res_id] = 1
            else:
                job_scores[job_id][res_id] = 0

    job_matching_score = {}
    
    for job_id in job_scores:
        score = sum(job_scores[job_id].values()) / len(job_scores[job_id]) if job_scores[job_id] else 0.
        job_matching_score[job_id] = score

    print("job_matching_score: ", job_matching_score)
    # 按照职责匹配度排序
    sorted_jobs = sorted(job_matching_score.items(), key=lambda x: x[1], reverse=True)
    # 返回前 top_k 个岗位的 id及匹配度
    
    return sorted_jobs[:top_k]


if __name__ == "__main__":
    search_keywords = ["Python", "Docker", "snowflake", "sql"]
    title = "service advisor"
    experiences=["I have strategic thinking training and application in project management", "I worked on several projects about data analysis and visualization", "I don't like customer service"]
    
    results = asyncio.run(
        get_jobs_by_experince_and_responsibilities_matching(experiences, distance_threshold=0.6)
     )
    
    #results = asyncio.run(
    #    get_jobs_by_title_similarity(title, distance_threshold=0.4)
    #)
    
    #results = asyncio.run(
    #    get_jobs_by_skill_matching(search_keywords, distance_threshold=0.25, top_k=10)
    #)
    
    print(results)
