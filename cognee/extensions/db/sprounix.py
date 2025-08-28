import asyncio

from cognee.extensions.db import get_sprounix_relational_engine


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


async def base_recall_jobs(job_type: list, titles: list, location: dict, limit: int = 1000):
    """
    base recall jobs, by job_type & titles * location
    """
    db_engine = get_sprounix_relational_engine()
    if not location:
        return []

    lng = location.get("lng")
    lat = location.get("lat")
    radius = location.get("radius") or 50000

    job_type_sql = ""
    if job_type:
        if len(job_type) == 1:
            job_type_sql = f"AND jd.job_type = '{job_type[0]}'"
        else:
            job_type_sql = f"AND jd.job_type IN {tuple(job_type)}"

    job_title_sql = ""
    if titles:
        key_titles = f'%({"|".join(titles)})%'
        job_title_sql = f"AND jd.title SIMILAR TO '{key_titles}'"

    sql = f"""
        SELECT 
            loc.job_id,
            ST_Distance(
                loc.geom::geography, 
                ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography
            ) AS distance_meters
        FROM job_locations AS loc, 
             job_details as jd
        WHERE jd.id = loc.job_id
            {job_title_sql}
            AND ST_DWithin(
                    loc.geom::geography, 
                    ST_SetSRID(ST_MakePoint({lng}, {lat}), 4326)::geography, 
                    {radius}
                )
            AND NOT EXISTS (SELECT 1 FROM recommend_jobs WHERE job_id = jd.id)
            {job_type_sql} 
        ORDER BY distance_meters
        limit {limit}
    """
    results = await db_engine.execute_query(sql)
    return results


if __name__ == '__main__':
    job_type = ['Full-time', 'Part-time']
    titles = ["Operations Manager"]
    location = dict(lng=-122.2913078, lat=37.8271784, radius=50000)
    asyncio.run(
        base_recall_jobs(job_type, titles, location)
    )
