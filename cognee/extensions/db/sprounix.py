import asyncio

from cognee.extensions.db import get_sprounix_relational_engine
from cognee.shared.logging_utils import get_logger


logger = get_logger("sprounix")


def generate_tsquery(queries):
    # 处理职位标题
    item_queries = []
    for item in queries:
        # 分割多词职位标题并用 & 连接
        words = item.lower().split()
        item_query = " & ".join(words)
        item_queries.append(f"({item_query})")
    tsquery = " | ".join(item_queries)
    return tsquery


async def get_user_locations(app_user_id: str):
    """
    get user locations
    """
    db_engine = get_sprounix_relational_engine()

    sql = f"""
        SELECT 
            id,
            location,
            radius,
            ST_X(geom) AS lng,
            ST_Y(geom) AS lat
        FROM user_locations 
        WHERE app_user_id = '{app_user_id}'
    """
    results = await db_engine.execute_query(sql)
    return results


async def base_recall_jobs(app_user_id: str, job_type: list, titles: list, skills: list, location: dict,
                           limit: int = 1000, posted_time_last_days=30):
    """
    base recall jobs, by job_type & titles * location
    """
    db_engine = get_sprounix_relational_engine()
    if not location:
        return []

    lng = location.get("lng")
    lat = location.get("lat")
    radius = location.get("radius") or 50000
    posted_time_last_days = posted_time_last_days or 30
    titles = titles or []
    core_skills = skills or []

    job_type_sql = ""
    if job_type:
        if len(job_type) == 1:
            job_type_sql = f"AND jd.job_type = '{job_type[0]}'"
        else:
            job_type_sql = f"AND jd.job_type IN {tuple(job_type)}"

    to_tsquery_items = titles + core_skills
    items = list(set([item.lower() for item in to_tsquery_items if item]))
    tsquery_cond = generate_tsquery(items)

    weights = "{0, 0, 0.7, 1.0}"  # D C B A

    sql = f"""
        SELECT 
            loc.job_id,
            jd.title,
            ST_Distance(
                loc.geom::geography, 
                ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography
            ) AS distance_meters,
            ts_rank_cd('{weights}', jsi.weighted_tsvector, query) AS relevance_score
        FROM job_locations AS loc
        JOIN job_details AS jd ON jd.id = loc.job_id 
        JOIN job_search_index jsi ON jd.id = jsi.job_id 
        CROSS JOIN to_tsquery('english', '{tsquery_cond}') AS query
        WHERE jd.posted_time >= NOW() - INTERVAL '{posted_time_last_days} days'
            AND ST_DWithin(
                    loc.geom::geography, 
                    ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography, 
                    {radius}
                )
            AND NOT EXISTS (SELECT 1 FROM recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            {job_type_sql}
            AND jsi.weighted_tsvector @@ query
        ORDER BY relevance_score
        limit {limit}
    """
    logger.info(sql)
    results = await db_engine.execute_query(sql)
    return results


if __name__ == '__main__':
    app_user_id = ""
    job_type = ['Full-time', 'Part-time']
    titles = ["Operations Manager"]
    core_skills = ["Django", "Python", "Docker"]
    location = dict(lng=-122.2913078, lat=37.8271784, radius=50000)
    asyncio.run(
        base_recall_jobs(app_user_id, job_type, titles, core_skills, location)
    )
