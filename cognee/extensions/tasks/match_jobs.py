from typing import Dict, List

from cognee.api.v1.recall.schemas import RecommendJobPayloadDTO
from cognee.extensions.tasks.recall_job import resume_skill_recall_job_ids, resume_job_titles_recall_job_ids
from cognee.shared.logging_utils import get_logger

logger = get_logger("match_job")


def get_job_level_code(job_level):
    """0 unknown 1 junior 2 mid 3 senior"""
    if not job_level:
        return 0
    job_levels = [job_level] if not isinstance(job_level, list) else job_level

    junior_levels = ["internship", "entry-level", "junior"]
    mid_levels = ["mid-level"]
    senior_levels = ["senior", "lead", "principal", "staff", "manager", "director", "executive"]

    for job_level in job_levels:
        job_level = job_level.lower()
        if job_level in junior_levels:
            return 1
        elif job_level in mid_levels:
            return 2
        elif job_level in senior_levels:
            return 3
    return 0


async def get_match_jobs(payload: RecommendJobPayloadDTO) -> List[Dict]:
    desired_position = payload.desired_position
    resume = payload.resume
    app_user_id = payload.app_user_id

    locations = desired_position.get("city") or []
    positions = desired_position.get("positions") or []
    industries = desired_position.get("industries") or []

    skills = resume.get("skills") or []
    work_experiences = resume.get("work_experiences") or []
    educations = resume.get("educations") or []
    job_level = resume.get("job_level") or []
    job_type = ""

    work_years = 0
    job_level_code = get_job_level_code(job_level)

    job_dict = {}
    if skills:
        job_skill_score_results = await resume_skill_recall_job_ids(skills, top_k=200)
        for job_skill_score_result in job_skill_score_results:
            job_id = job_skill_score_result["job_id"]
            job_dict[job_id] = {}
            job_dict[job_id]["skill"] = job_skill_score_result
        logger.info(f"{app_user_id} skill recall finish")
    if positions:
        job_title_score_results = await resume_job_titles_recall_job_ids(positions, top_k=500)
        for job_title_score_result in job_title_score_results:
            job_id = str(job_title_score_result["job_id"])
            if job_id not in job_dict:
                job_dict[job_id] = {}
            job_dict[job_id]["title"] = job_title_score_result
        logger.info(f"{app_user_id} job title recall finish")

    # logger.info(f"job_dict: {job_dict}")
    # recall_job_dict = {k: v for k, v in job_dict.items() if len(v.keys()) > 1}
    recall_job_dict = dict(sorted(job_dict.items(), key=lambda x: len(x[1].keys()), reverse=True))

    # recall_job_ids = list(recall_job_dict.keys())

    # jobs = await get_jobs(recall_job_ids)
    # if not jobs:
    #     return []
    # jobs = [job for job in jobs if get_job_level_code(job["job_level"]) == job_level_code]

    jobs = []
    for job_id, detail in recall_job_dict.items():
        skill = detail.get("skill") or {}
        skill_score = skill.get("score") or 0.8
        detail["reason"] = [f"matched {int(skill_score * 100)}% skill."]
        job = dict(job_id=job_id, score=skill_score, detail=detail)
        jobs.append(job)
    logger.info(f"jobs: {jobs}")
    return jobs


if __name__ == '__main__':
    import asyncio

    r = RecommendJobPayloadDTO()
    r.desired_position = {
        "positions": ["Customer Service"]
    }
    r.resume = {
        "skills": ['Word Processing', 'Microsoft Office Suites', 'Type 55 WPM', 'Spreadsheet', 'Patient Accounting System', 'Database'],
    }
    r.app_user_id = "test"
    results = asyncio.run(
        get_match_jobs(r)
    )
    print(results)
