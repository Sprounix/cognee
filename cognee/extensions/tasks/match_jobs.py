import datetime
from typing import Dict, List

from cognee.api.v1.recall.schemas import RecommendJobPayloadDTO
from cognee.extensions.cypher.job import get_jobs
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

def calc_date_diff_days(work_end, work_start):
    days = (work_end - work_start).days
    if days <= 0:
        return 0
    return round(days / 365, 1)


def calc_resume_work_years(work_exps):
    try:
        start_date_list = [w["start_date"] for w in work_exps if "start_date" in w and w["start_date"]]
        if not start_date_list:
            return 0
        first_start_date_str = sorted(start_date_list, reverse=False)[0]
        now = datetime.date.today()
        first_start_date = datetime.datetime.strptime(first_start_date_str, '%Y-%m-%d').date()
        years = calc_date_diff_days(now, first_start_date)
        return years
    except:
        return 0


def calc_work_year_score(jd_work_years, resume_work_years):
    """
    calc work years score
    :param jd_work_years: {'low': 1, 'high': 3} high -1 不限
    :param resume_work_years: resume work years
    :return:
    """
    diff_low_dict = {0: 1, 1: 0.9, 2: 0.8, 3: 0.7, 4: 0.5, 5: 0.1, 6: 0.1}
    diff_high_dict = {0: 1, 1: 1, 2: 0.95, 3: 0.8, 4: 0.7, 5: 0.1, 6: 0.1}
    epi = 0.00001
    low = jd_work_years['low']
    high = jd_work_years['high']
    diff_low = low - resume_work_years
    diff_high = resume_work_years - high
    if diff_low > 0:
        if diff_low >= 6:
            return 0.01
        else:
            return diff_low_dict[round(diff_low + epi)]
    if diff_high > 0 and high > 0:
        diff_high = round(diff_high + epi)
        if diff_high >= 6:
            return 0.05
        else:
            return diff_high_dict[diff_high]
    return 1


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

    user_work_years = calc_resume_work_years(work_experiences)
    user_job_level_code = get_job_level_code(job_level)

    job_dict = {}
    if skills:
        job_skill_score_results = await resume_skill_recall_job_ids(skills, top_k=200)
        for job_skill_score_result in job_skill_score_results:
            job_id = job_skill_score_result["job_id"]
            job_dict[job_id] = {}
            job_dict[job_id]["skill"] = job_skill_score_result
            job_dict[job_id]["score"] = job_skill_score_result.get("score") * 0.5
        logger.info(f"app_user_id:{app_user_id} skill recall finish, total: {len(job_skill_score_results)}")
    if positions:
        job_title_score_results = await resume_job_titles_recall_job_ids(positions, top_k=500)
        for job_title_score_result in job_title_score_results:
            job_id = str(job_title_score_result["job_id"])
            if job_id not in job_dict:
                job_dict[job_id] = {}
            score = job_dict[job_id].get("score") or 0
            job_dict[job_id]["title"] = job_title_score_result
            job_dict[job_id]["score"] = score + (job_title_score_result.get("score") * 0.5)
        logger.info(f"app_user_id:{app_user_id} job title recall finish, total: {len(job_title_score_results)}")
    logger.info(f"app_user_id:{app_user_id} recall jobs total: {len(job_dict)}")

    recall_job_ids = list(job_dict.keys())
    jobs = await get_jobs(recall_job_ids)
    logger.info(f"app_user_id:{app_user_id} get jobs from graphdb total: {len(jobs)}")
    if not jobs:
        return []
    match_results = []
    for job in jobs:
        job_id = job["id"]
        score_detail = job_dict.get(job_id)
        score = score_detail.get("score")

        job_level = job.get("job_level")
        if job_level and user_job_level_code:
            job_level_code = get_job_level_code(job_level)
            if user_job_level_code > job_level_code:
                score = score - 0.5

        required_list = job.get("qualification", {}).get("required")
        items = [
            i.get("item") for i in required_list if i.get("category") and i.get("category") == "Experience" and i.get("item")
        ]
        job_work_years = 0
        if user_work_years:
            pass
        work_locations = job.get("work_locations") or []

        skill = score_detail.get("skill") or {}
        skill_score = skill.get("score") or 0.8

        score_detail["reason"] = [f"matched {int(skill_score * 100)}% skill."]
        job = dict(job_id=job_id, score=max(0.05, score), detail=score_detail)
        match_results.append(job)

    logger.info(f"app_user_id:{app_user_id} match jobs total: {len(match_results)}")
    return match_results


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
