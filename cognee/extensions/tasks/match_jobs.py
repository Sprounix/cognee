import datetime
import time
from typing import Dict, List

from cognee.api.v1.recall.schemas import RecommendJobPayloadDTO
from cognee.extensions.cypher.job import get_jobs, get_responsibility_items
from cognee.extensions.tasks.recall_job import (
    resume_skill_recall_job_ids,
    resume_desired_positions_and_job_title_recall_job_ids,
    resume_desired_positions_and_job_function_recall_job_ids,
    resume_work_experiences_recall_job_ids
)
from cognee.extensions.utils.extract import extract_experience_years, split_sentences
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
    high = jd_work_years['high'] or -1
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


def calc_job_level(job_level_code, user_job_level_code):
    if job_level_code == user_job_level_code:
        return 1
    elif user_job_level_code == 3 and user_job_level_code > job_level_code:
        return 0.6
    elif user_job_level_code <= 1 and job_level_code == 3:
        return 0.6
    elif job_level_code > user_job_level_code:
        return 1
    return 0.8


def get_job_work_years(job):
    if not job:
        return
    qualification = job.get("qualification") or {}
    if not qualification:
        return
    work_year_list = []
    for col in ["required", "preferred"]:
        item_list = qualification.get(col) or []
        if not item_list:
            continue
        items = [
            i.get("item") for i in item_list if
            i.get("category") and i.get("category") == "Experience" and i.get("item")
        ]
        for item in items:
            e_result = extract_experience_years(item)
            if not e_result:
                continue
            work_year_list.append(e_result)
    if not work_year_list:
        return
    # 获取最大的工作年限
    work_year_list = sorted(work_year_list, key=lambda x: x["low"], reverse=True)
    return work_year_list[0]


def get_last_work_experience(work_experiences):
    if not work_experiences:
        return {}
    experiences = [w for w in work_experiences if w.get("start_date")]
    if not experiences:
        return
    experiences = sorted(experiences, key=lambda x: x["start_date"], reverse=True)
    last_experience = experiences[0]
    return last_experience


def calc_basic_score_by_weight(score_detail, weight_dict=None):
    score_detail = score_detail or {}
    weight_dict = weight_dict or {
        "title": 0.25, "skill": 0.25,  "experience": 0.25, "yoe_score": 0.25,
    }

    job_title_match = 1 if score_detail.get("title") else 0
    job_function_match = 1 if score_detail.get("function") else 0
    job_title_score = job_title_match * 0.7 + job_function_match * 0.3

    skill_score = score_detail.get("skill", {}).get("score") or 0
    relevant_experience_score = score_detail.get("experience", {}).get("score") or 0
    yoe_score = score_detail.get("yoe_score") or 0

    score = job_title_score * weight_dict["title"] + \
              skill_score * weight_dict["skill"] + \
              relevant_experience_score * weight_dict["experience"] + \
              yoe_score * weight_dict["yoe_score"]
    return score


def generate_reasons(score_detail, match_responsibility_dict):
    reasons = []
    skill = score_detail.get("skill")
    if skill:
        if skill.get("score") > 0.5:
            reasons.append(f'Core skill matched.')
        else:
            reasons.append(f'Part skill matched.')
    experience = score_detail.get("experience")
    if experience:
        responsibility_ids = experience.get("responsibility_ids") or []
        for responsibility_id in responsibility_ids:
            responsibility_item = match_responsibility_dict.get(responsibility_id)
            if not responsibility_item:
                continue
            reasons.append(f'Responsibility matched: {responsibility_item}')
    return reasons


async def get_match_jobs(payload: RecommendJobPayloadDTO) -> List[Dict]:
    start = time.perf_counter()
    desired_position = payload.desired_position
    resume = payload.resume
    app_user_id = payload.app_user_id
    top_k = 100

    locations = desired_position.get("city") or []
    positions = desired_position.get("positions") or []
    industries = desired_position.get("industries") or []

    skills = resume.get("skills") or []
    work_experiences = resume.get("work_experiences") or []
    educations = resume.get("educations") or []
    # job_level = resume.get("job_level") or []
    desired_job_type = desired_position.get("job_type")

    user_work_years = calc_resume_work_years(work_experiences)

    positions = list(set(positions))

    last_work_experience = get_last_work_experience(work_experiences)
    last_work_experience_description = last_work_experience.get("description") or ""
    last_work_experience_job_title = last_work_experience.get("job") or ""

    if last_work_experience_job_title:
        split_positions = last_work_experience_job_title.split("/")
        for position in split_positions:
            positions.append(position.strip())

    positions = list(set(positions))

    job_dict = {}
    if skills:
        logger.info(f"app_user_id:{app_user_id} skills: {skills}")
        job_skill_score_results = await resume_skill_recall_job_ids(skills, top_k=top_k)
        for job_skill_score_result in job_skill_score_results:
            job_id = job_skill_score_result["job_id"]
            if job_id not in job_dict:
                job_dict[job_id] = {}
            job_dict[job_id]["skill"] = job_skill_score_result
        logger.info(f"app_user_id:{app_user_id} skill recall finish, total: {len(job_skill_score_results)}")

    logger.info(f"app_user_id:{app_user_id} positions: {positions}")
    if positions:
        job_title_score_results = await resume_desired_positions_and_job_title_recall_job_ids(positions, top_k=top_k)
        for job_title_score_result in job_title_score_results:
            job_id = str(job_title_score_result["job_id"])
            if job_id not in job_dict:
                job_dict[job_id] = {}
            job_dict[job_id]["title"] = job_title_score_result
        logger.info(f"app_user_id:{app_user_id} job title recall finish, total: {len(job_title_score_results)}")

        job_function_score_results = await resume_desired_positions_and_job_function_recall_job_ids(positions, top_k=top_k)
        for job_function_score_result in job_function_score_results:
            job_id = str(job_function_score_result["job_id"])
            if job_id not in job_dict:
                job_dict[job_id] = {}
            job_dict[job_id]["function"] = job_function_score_result
        logger.info(f"app_user_id:{app_user_id} job function recall finish, total: {len(job_function_score_results)}")

    matched_all_responsibility_ids = []
    if last_work_experience_description:
        last_work_experience_contents = split_sentences(last_work_experience_description)
        logger.info(f"app_user_id:{app_user_id} last_work_experience_contents: {last_work_experience_contents}")
        experience_score_results = await resume_work_experiences_recall_job_ids(last_work_experience_contents, top_k=top_k)
        for experience_score_result in experience_score_results:
            job_id = str(experience_score_result["job_id"])
            if job_id not in job_dict:
                job_dict[job_id] = {}
            job_dict[job_id]["experience"] = experience_score_result
            responsibility_ids = experience_score_result.get("responsibility_ids")
            for responsibility_id in responsibility_ids:
                if responsibility_id not in matched_all_responsibility_ids:
                    matched_all_responsibility_ids.append(responsibility_id)

        logger.info(f"app_user_id:{app_user_id} experience recall finish, total: {len(experience_score_results)}")

    logger.info(f"app_user_id:{app_user_id} recall jobs total: {len(job_dict)}")

    logger.info(
        f"app_user_id:{app_user_id} matched all responsibility_ids total: {len(matched_all_responsibility_ids)}"
    )
    match_responsibility_dict = {}
    if matched_all_responsibility_ids:
        match_responsibility_items = await get_responsibility_items(matched_all_responsibility_ids)
        match_responsibility_dict = {res["id"]: res["item"] for res in match_responsibility_items}

    recall_job_ids = list(job_dict.keys())
    jobs = await get_jobs(recall_job_ids)
    logger.info(f"app_user_id:{app_user_id} get jobs from graphdb total: {len(jobs)}")
    if not jobs:
        return []
    match_results = []
    for job in jobs:
        job_id = job["id"]
        score_detail = job_dict.get(job_id)

        # job_level = job.get("job_level")
        # if job_level:
        #     user_job_level_code = get_job_level_code(job_level)
        #     job_level_code = get_job_level_code(job_level)
        #     score_detail["level_score"] = calc_job_level(job_level_code, user_job_level_code)
        #     score = score * score_detail["level_score"]

        job_work_years = get_job_work_years(job)
        # logger.info(f"app_user_id:{app_user_id} job_work_years: {job_work_years} user_work_years:{user_work_years}")
        if job_work_years:
            score_detail["yoe_score"] = calc_work_year_score(job_work_years, user_work_years)

        # base score
        score_detail["b_score"] = calc_basic_score_by_weight(score_detail)

        score = score_detail["b_score"]
        score_detail["location_score"] = 1
        if locations:
            score_detail["location_score"] = 0
            work_locations = job.get("work_locations") or []
            work_location_name_list = [wl["name"] for wl in work_locations]
            # logger.info(f"app_user_id:{app_user_id} locations: {locations} work_locations:{work_location_name_list}")
            for desired_location in locations:
                if desired_location in work_location_name_list:
                    score_detail["location_score"] = 1
                    break
            # if score_detail["location_score"] == 0:
            #     score = score * 0.1

        job_type = job.get("job_type") or []
        if desired_job_type and desired_job_type != "Not sure yet" and desired_job_type not in job_type:
            score_detail["job_type_score"] = 0
            # score = score * score_detail["job_type"]

        score_detail["score"] = score
        score_detail["reason"] = generate_reasons(score_detail, match_responsibility_dict)
        job = dict(job_id=job_id, score=max(0, score), detail=score_detail)
        match_results.append(job)

    elapsed = time.perf_counter() - start
    logger.info(f"app_user_id: {app_user_id} match jobs total: {len(match_results)} elapsed: {elapsed:.6f}s")
    return match_results


if __name__ == '__main__':
    import asyncio

    d = {'app_user_id': 'c525dc05-3bbe-446e-84bf-ab0fdbd5e75a',
     'desired_position': {'id': 'c89daf3b-08dc-4f11-bb7f-6676eafa0aa9',
                          'app_user_id': 'c525dc05-3bbe-446e-84bf-ab0fdbd5e75a', 'city': [],
                          'positions': ['Custom Service'], 'industries': [], 'salary': None,
                          'select_positions': ['946f0f96-0d83-4251-bc39-f54e0e0431e1'], 'job_status': None,
                          'job_type': None, 'created_at': '2025-07-24T07:54:11.332186Z',
                          'updated_at': '2025-07-29T07:26:45.017036Z'},
     'resume': {'id': '3980a7a9-0784-42f6-954e-a7362f607b04',
                'app_user_id': 'c525dc05-3bbe-446e-84bf-ab0fdbd5e75a',
                'skills': ['Word Processing', 'Microsoft Office Suites', 'Type 55 WPM', 'Spreadsheet',
                           'Patient Accounting System', 'Database'], 'others': '',
                'educations': [{'id': '59fd6686-2651-47b2-8d4d-92545e82e82a',
                                'college_name': 'The Hong Kong University of Science and Technology (HKUST)',
                                'degree': 'Master of Engineering', 'major_name': 'Mechanical Engineering',
                                'description': None, 'start_date': '2009-01-01', 'end_date': '2011-01-01',
                                'present': False}, {'id': '1135c3d7-5f22-4306-918c-233935c016a7',
                                                    'college_name': 'Shanghai Jiao Tong University (SJTU)',
                                                    'degree': 'Bachelor of Engineering',
                                                    'major_name': 'Mechanical Engineering Mechatronics',
                                                    'description': None, 'start_date': '2005-01-01',
                                                    'end_date': '2009-01-01', 'present': False}],
                'work_experiences': [
             {'id': 'ed09b716-f742-4238-ae61-c788956740f3', 'company_name': 'SAIC Motor',
              'department_name': 'chexiang.com', 'job': 'Web Developer/Frontend Developer',
              'description': 'Frontend Developer\nResponsibility: web page dev/UI component dev based on jQuery\nTech Stack: Jade/SCSS/jQuery/Gulp',
              'start_date': '2012-01-01', 'end_date': '2014-01-01', 'present': False},
             {'id': '48a6632b-f5db-460a-acc4-df5e87c43685', 'company_name': 'Siemens China',
              'department_name': 'Industry Sector', 'job': 'Management Trainee/Tech Support Engineer',
              'description': 'A member of MC20 trainee program. Joined the Shanghai Crane team afterwards as a\ntech support engineer, providing technical consulting for BD partners.',
              'start_date': '2011-01-01', 'end_date': '2012-01-01', 'present': False}],
                'project_experiences': []
                }
         }

    r = RecommendJobPayloadDTO(**d)
    results = asyncio.run(
        get_match_jobs(r)
    )
    print(results)
