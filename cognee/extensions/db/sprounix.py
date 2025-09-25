import asyncio
import re

from cognee.extensions.db import get_sprounix_relational_engine
from cognee.extensions.tasks.match_jobs import calc_job_level
from cognee.shared.logging_utils import get_logger


logger = get_logger("sprounix")


def generate_tsquery(queries):
    def escape_tsquery_term(term):
        """转义单个TSQuery术语中的特殊字符"""
        # PostgreSQL TSQuery需要转义的特殊字符: ! & | ( ) : * < >
        # 将特殊字符替换为空格或进行适当处理
        term = re.sub(r'[!&|():*<>]', ' ', term)
        # 移除多余空格并确保不为空
        term = re.sub(r'\s+', ' ', term).strip()
        return term

    item_queries = []
    for item in queries:
        # 转义整个项目中的特殊字符
        safe_item = escape_tsquery_term(item.lower())
        if not safe_item:  # 如果转义后为空，跳过
            continue

        # 分割多词职位标题并用 & 连接
        words = safe_item.split()
        # 过滤掉空词
        words = [word for word in words if word]
        if not words:  # 如果没有有效词汇，跳过
            continue

        item_query = " & ".join(words)
        item_queries.append(f"({item_query})")

    if not item_queries:
        return ""  # 或返回一个默认查询，如 "''"

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


async def get_jobs(job_ids):
    """
    get jobs
    """
    db_engine = get_sprounix_relational_engine()
    if len(job_ids) == 1:
        id_sql = f"jd.id = '{job_ids[0]}'"
    else:
        id_sql = f"jd.id IN {tuple(job_ids)}"
    sql = f"""
        SELECT
            jd.company_id, 
            jd.id,
            jd.title,
            jd.job_level,
            jd.location,
            jd.job_type,
            jd.job_function,
            jd.job_md5,
            jd.posted_time,
            jde.result
        FROM job_detail_extract_result AS jde 
        JOIN job_details AS jd ON jd.id = jde.id
        WHERE {id_sql}
    """
    results = await db_engine.execute_query(sql)
    for job in results:
        result = job.pop("result")
        skills = result.get("skills") or []
        majors = result.get("majors") or []
        responsibilities = result.get("responsibilities") or []
        qualification = result.get("qualification") or {}
        work_years = result.get("work_years") or ""
        job_level = result.get("job_level") or ""
        job["skills"] = skills
        job["majors"] = majors
        job["qualification"] = qualification
        job["responsibilities"] = responsibilities
        job["work_years"] = work_years
        job["e_job_level"] = job_level
    return results


async def base_recall_jobs_exclude_location(
        app_user_id: str, job_type: list, titles: list, limit: int = 1000, posted_time_last_days=30
):
    """
    base recall jobs, by job_type & titles * location
    """
    db_engine = get_sprounix_relational_engine()
    posted_time_last_days = posted_time_last_days or 30
    titles = titles or []

    job_type_sql = ""
    if job_type:
        if len(job_type) == 1:
            job_type_sql = f"AND jd.job_type = '{job_type[0]}'"
        else:
            job_type_sql = f"AND jd.job_type IN {tuple(job_type)}"

    to_tsquery_items = titles
    items = list(set([item.lower() for item in to_tsquery_items if item]))
    tsquery_cond = generate_tsquery(items)

    weights = "{0, 0, 0.7, 1.0}"  # D C B A

    sql = f"""
        SELECT 
            jd.id AS job_id,
            -- jd.title,
            ts_rank_cd('{weights}', jsi.weighted_tsvector, query) AS relevance_score
        FROM (
            SELECT DISTINCT ON (location, job_md5)
                id, title, location, job_md5, posted_time, job_type, status
            FROM job_details 
            WHERE posted_time >= NOW() - INTERVAL '{posted_time_last_days} days' 
            ORDER BY location, job_md5, posted_time DESC, id DESC
        ) AS jd  
        JOIN job_weighted_vector jsi ON jd.id = jsi.job_id 
        CROSS JOIN to_tsquery('english', '{tsquery_cond}') AS query
        WHERE jd.posted_time >= NOW() - INTERVAL '{posted_time_last_days} days'
            AND NOT EXISTS (SELECT 1 FROM recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            AND NOT EXISTS (SELECT 1 FROM precomputed_recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            AND jd.status = 'active'
            {job_type_sql}
            AND jsi.weighted_tsvector @@ query
        ORDER BY relevance_score DESC
        limit {limit}
    """
    logger.info(sql)
    results = await db_engine.execute_query(sql)
    return results


async def base_recall_jobs_location(app_user_id: str, job_type: list, location: dict, limit: int = 1000,
                                    posted_time_last_days=30):
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

    job_type_sql = ""
    if job_type:
        if len(job_type) == 1:
            job_type_sql = f"AND jd.job_type = '{job_type[0]}'"
        else:
            job_type_sql = f"AND jd.job_type IN {tuple(job_type)}"
    sql = f"""
        SELECT 
            jd.id AS job_id,
            -- jd.title,
            ST_Distance(
                loc.geom::geography, 
                ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography
            ) AS distance_meters
        FROM (
            SELECT DISTINCT ON (location, job_md5)
                id, title, location, job_md5, posted_time, job_type, status
            FROM job_details 
            WHERE posted_time >= NOW() - INTERVAL '{posted_time_last_days} days' 
            ORDER BY location, job_md5, posted_time DESC, id DESC
        ) AS jd 
        JOIN job_locations AS loc ON jd.id = loc.job_id 
        WHERE jd.posted_time >= NOW() - INTERVAL '{posted_time_last_days} days'
            AND ST_DWithin(
                    loc.geom::geography, 
                    ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography, 
                    {radius}
                )
            AND NOT EXISTS (SELECT 1 FROM recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            AND NOT EXISTS (SELECT 1 FROM precomputed_recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            AND jd.status = 'active'
            {job_type_sql}
        ORDER BY posted_time DESC
        limit {limit}
    """
    logger.info(sql)
    results = await db_engine.execute_query(sql)
    return results


async def base_recall_jobs(app_user_id: str, job_type: list, titles: list, skills: list, location: dict,
                           user_post_graduation_work_years: float, limit: int = 1000, posted_time_last_days=30):
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

    if user_post_graduation_work_years < 1.5:
        job_level_sql = f"AND jd.job_level IN ('Entry level', 'Not Applicable')"
    else:
        job_level_sql = f"AND jd.job_level NOT IN ('Entry level')"

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
            jd.id AS job_id,
            -- jd.title,
            ST_Distance(
                loc.geom::geography, 
                ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography
            ) AS distance_meters,
            ts_rank_cd('{weights}', jsi.weighted_tsvector, query) AS relevance_score
        FROM (
            SELECT DISTINCT ON (location, job_md5)
                id, title, location, job_md5, posted_time, job_type, status
            FROM job_details 
            WHERE posted_time >= NOW() - INTERVAL '{posted_time_last_days} days' 
            ORDER BY location, job_md5, posted_time DESC, id DESC
        ) AS jd 
        JOIN job_locations AS loc ON jd.id = loc.job_id 
        JOIN job_weighted_vector jsi ON jd.id = jsi.job_id 
        CROSS JOIN to_tsquery('english', '{tsquery_cond}') AS query
        WHERE jd.posted_time >= NOW() - INTERVAL '{posted_time_last_days} days'
            AND ST_DWithin(
                    loc.geom::geography, 
                    ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography, 
                    {radius}
                )
            AND NOT EXISTS (SELECT 1 FROM recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            AND NOT EXISTS (SELECT 1 FROM precomputed_recommend_jobs WHERE app_user_id='{app_user_id}' AND job_id = jd.id)
            AND jd.status = 'active'
            {job_type_sql}
            {job_level_sql}
            AND jsi.weighted_tsvector @@ query
        ORDER BY relevance_score DESC
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
