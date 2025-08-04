from typing import List, Dict

from cognee.extensions.cypher.job import (
    get_job_ids_by_skills, get_job_skill_ids, get_job_ids_by_job_function, get_job_responsibility_ids,
    get_job_ids_by_responsibility
)
from cognee.extensions.vector.job import (
    get_job_skill_distance_results, get_job_title_distance_results, get_job_function_distance_results,
    get_responsibility_distance_results
)


async def resume_skill_recall_job_ids(skill_tags: List[str], top_k=50) -> List[Dict]:
    if not skill_tags:
        return []
    scored_results = await get_job_skill_distance_results(skill_tags, top_k=top_k)
    if not scored_results:
        return []
    recall_skill_ids = [str(item.id) for item in scored_results]
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


async def resume_desired_positions_and_job_title_recall_job_ids(desired_positions: List[str], top_k=50) -> List[Dict]:
    if not desired_positions:
        return []
    scored_results = await get_job_title_distance_results(desired_positions)
    if not scored_results:
        return []
    match_jobs = [{"job_id": item.id, "score": round(1 - item.score, 2)} for item in scored_results]
    sorted_jobs = sorted(match_jobs, key=lambda x: x["score"], reverse=True)
    return sorted_jobs[:top_k]


async def resume_desired_positions_and_job_function_recall_job_ids(desired_positions: List[str], top_k=50) -> List[Dict]:
    if not desired_positions:
        return []
    scored_results = await get_job_function_distance_results(desired_positions)
    if not scored_results:
        return []
    job_function_ids = [str(item.id) for item in scored_results]
    job_ids = await get_job_ids_by_job_function(job_function_ids)
    match_jobs = [{"job_id": job_id, "score": 1} for job_id in job_ids]
    return match_jobs[:top_k]


async def resume_work_experiences_recall_job_ids(work_exp_descriptions: List[str], top_k=50) -> List[Dict]:
    if not work_exp_descriptions:
        return []
    scored_results = await get_responsibility_distance_results(work_exp_descriptions)
    if not scored_results:
        return []
    recall_responsibility_ids = [str(item.id) for item in scored_results]
    job_ids = await get_job_ids_by_responsibility(recall_responsibility_ids)
    job_responsibility_ids = await get_job_responsibility_ids(job_ids)
    job_responsibility_dict = {
        jr["job_id"]: jr["responsibility_ids"] for jr in job_responsibility_ids if jr["responsibility_ids"]
    }
    match_job_responsibility_ids = []
    for job_id, responsibility_ids in job_responsibility_dict.items():
        curr_job_match_responsibility_ids = [r_id for r_id in responsibility_ids if r_id in recall_responsibility_ids]
        score = round(len(curr_job_match_responsibility_ids) / len(responsibility_ids), 2)
        result = dict(job_id=job_id, responsibility_ids=curr_job_match_responsibility_ids, score=score)
        match_job_responsibility_ids.append(result)
    sorted_jobs = sorted(match_job_responsibility_ids, key=lambda x: x["score"], reverse=True)
    return sorted_jobs[:top_k]
