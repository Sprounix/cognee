from typing import List, Dict

from cognee.extensions.cypher.job import get_job_ids_by_skills, get_job_skill_ids
from cognee.extensions.vector.job import get_job_skill_distance_results, get_job_title_distance_results


async def resume_skill_recall_job_ids(skill_tags: List[str], top_k=500) -> List[Dict]:
    if not skill_tags:
        return []
    scored_results = await get_job_skill_distance_results(skill_tags, top_k=top_k)
    print("scored_results:", scored_results)
    recall_skill_ids = [str(item.id) for item in scored_results]
    if not recall_skill_ids:
        return []
    job_ids = await get_job_ids_by_skills(recall_skill_ids)
    job_skill_ids = await get_job_skill_ids(job_ids)

    job_skills_dict = {jk["job_id"]: jk["skills"] for jk in job_skill_ids if jk["skills"]}

    match_job_skills = []
    for job_id, job_skills in job_skills_dict.items():
        curr_job_match_skills = [skill_id for skill_id in job_skills if skill_id in recall_skill_ids]
        score = round(len(curr_job_match_skills)/len(job_skills), 2)
        result = dict(job_id=job_id, skills=curr_job_match_skills, score=score)
        match_job_skills.append(result)
    sorted_jobs = sorted(match_job_skills, key=lambda x: x["score"], reverse=True)
    return sorted_jobs[:top_k]



async def resume_job_titles_recall_job_ids(job_titles: List[str], top_k=500) -> List[Dict]:
    if not job_titles:
        return []
    scored_results = await get_job_title_distance_results(job_titles)
    if not scored_results:
        return []
    match_jobs = [{"job_id": item.id, "score": round(1 - item.score, 2)} for item in scored_results]
    sorted_jobs = sorted(match_jobs, key=lambda x: x["score"], reverse=True)
    return sorted_jobs[:top_k]