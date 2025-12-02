import asyncio
import time
from typing import Dict, List, Tuple

from cognee.api.v1.recall.schemas import RecommendJobPayloadDTO
from cognee.extensions.cypher.job import get_internship_jobs
from cognee.extensions.db.sprounix import (
    base_recall_jobs, get_user_locations, get_jobs, base_recall_jobs_exclude_location
)
from cognee.extensions.utils.extract import extract_experience_years
from cognee.shared.logging_utils import get_logger
from cognee.extensions.utils.resume_parse import (
    calc_first_degree_graduate_date,
    calc_resume_work_years
)

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

def calc_work_year_score(jd_work_years, resume_work_years):
    """
    calc work years score
    :param jd_work_years: {'low': 1, 'high': 3} high -1 不限
    :param resume_work_years: resume work years
    :return:
    """
    low = jd_work_years['low']
    diff_years = int(low - resume_work_years)
    if not resume_work_years:
        if not low:
            return 1
        elif low > 2:
            return 0.01
        else:
            weight = {1: 0.8, 2: 0.5}
            return weight.get(low) or 0.6
    elif 3 <= resume_work_years <= 5:
        _diff_years = abs(diff_years)
        if _diff_years > 2:
            return 0.01
        weight = {0: 1, 1: 0.8, 2: 0.5}
        return weight.get(_diff_years) or 0.6
    else:
        if diff_years > 0:
            if diff_years > 2:
                return 0.01
            else:
                weight = {0: 1, 1: 0.8, 2: 0.5}
                return weight.get(diff_years) or 0.6
        else:
            _diff_years = abs(diff_years)
            if _diff_years > 2:
                return 0.6
            weight = {0: 1, 1: 0.8, 2: 0.6}
            return weight.get(_diff_years) or 0.6

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
        "relevance": 0.5, "skill": 0.25,  "experience": 0.25, "yoe_score": 0.25,
    }
    relevance_score = min(float(score_detail.get("relevance_score") or 0)/20, 1)

    # job_title_match = 1 if score_detail.get("title") else 0
    # job_function_match = 1 if score_detail.get("function") else 0
    # job_title_score = job_title_match * 0.7 + job_function_match * 0.3

    skill_score = score_detail.get("skill", {}).get("score") or 0
    relevant_experience_score = score_detail.get("experience", {}).get("score") or 0
    yoe = score_detail.get("yoe") or {}
    yoe_score = yoe.get("score") or 0
    score = relevance_score * weight_dict["relevance"] + \
              skill_score * weight_dict["skill"] + \
              yoe_score * weight_dict["yoe_score"]
    return score


def generate_reasons(score_detail, job):
    reasons = []
    skill = score_detail.get("skill")
    if skill:
        if skill.get("score") > 0.5:
            reasons.append(f'Core skill matched.')
        else:
            reasons.append(f'Part skill matched.')
    experience = score_detail.get("experience")
    if experience:
        job_responsibilities = job.get("responsibilities") or []
        r_dict = {r["id"]: r["item"] for r in job_responsibilities}
        responsibility_ids = experience.get("responsibility_ids") or []
        for responsibility_id in responsibility_ids:
            responsibility_item = r_dict.get(responsibility_id)
            if not responsibility_item:
                continue
            reasons.append(f'Responsibility matched: {responsibility_item}')
    return reasons


def state_match(desired_locations, work_locations):
    desired_location_state_list = []
    work_location_state_list = []
    for l in desired_locations:
        states = l.split(",")
        if len(states) > 1:
            state = states[1].lower().strip()
            desired_location_state_list.append(state)
    for l in work_locations:
        states = l.split(",")
        if len(states) > 1:
            state = states[1].lower().strip()
            work_location_state_list.append(state)
    if not desired_location_state_list and not work_location_state_list:
        return True
    return bool(set(desired_location_state_list) & set(work_location_state_list))


async def get_match_internship_jobs():
    recall_job_ids = await get_internship_jobs()
    return recall_job_ids


def find_matching_skills(resume_skills: List[str], job_skills: List[str],
                         synonym_map: Dict[str, List[str]] = None) -> Tuple[float, List[str]]:
    """
    计算技能相似度并返回匹配的技能对

    参数:
        resume_skills: 简历中的技能列表
        job_skills: 工作要求的技能列表
        synonym_map: 同义词映射表

    返回:
        相似度分数(0-1)和匹配的技能对列表
    """
    # 默认同义词映射（可根据行业扩展）
    synonym_map = synonym_map or {
        "machine learning": ["ml", "machine learning algorithms"],
        "data analysis": ["data analytics", "analyzing data"],
        "sql": ["structured query language"],
        "python": ["python programming"]
    }

    # 统一处理函数：标准化技能名称
    def normalize(skill: str) -> str:
        skill_lower = skill.lower()
        for standard, variants in synonym_map.items():
            if skill_lower == standard.lower() or skill_lower in [v.lower() for v in variants]:
                return standard.lower()
        return skill_lower

    # 标准化技能列表并保留原始值（用于展示）
    resume_normalized = [(skill, normalize(skill)) for skill in resume_skills]
    job_normalized = [(skill, normalize(skill)) for skill in job_skills]

    # 查找匹配的技能对
    matched_resume_skills = []
    matched_job_skills = set()  # 避免工作技能被重复匹配

    # 优先匹配完全一致或同义词
    for res_skill, res_norm in resume_normalized:
        for job_skill, job_norm in job_normalized:
            if res_norm == job_norm and job_skill not in matched_job_skills:
                matched_resume_skills.append(res_skill)
                matched_job_skills.add(job_skill)
                break

    # 计算相似度（匹配数量 / 总技能数）
    total_skills = len(set(res[1] for res in resume_normalized) | set(job[1] for job in job_normalized))
    similarity = len(matched_resume_skills) / total_skills if total_skills > 0 else 0.0

    return similarity, matched_resume_skills


async def base_recall_jobs_multi_location(
        app_user_id: str, job_type: list, titles: list, skills: list, locations: list,
        user_post_graduation_work_years: float, find_internship_job: bool, limit: int = 1000
):
    """
    multi location
    :return [{"job_id": "", "distance_meters": 10000}, ]
    """
    recall_results = await asyncio.gather(
        *[base_recall_jobs(
            app_user_id=app_user_id, job_type=job_type, titles=titles, skills=skills, location=location,
            user_post_graduation_work_years=user_post_graduation_work_years, find_internship_job=find_internship_job,
            limit=limit
        ) for location in locations]
    )
    merged = [item for sublist in recall_results for item in sublist]
    merged = sorted(merged, key=lambda x: x["relevance_score"], reverse=True)
    return merged


def fix_job_level(job_level, e_job_level):
    if job_level == "Not Applicable" and e_job_level != "Not Applicable":
        return e_job_level
    return job_level


async def get_match_jobs(payload: RecommendJobPayloadDTO) -> List[Dict]:
    start = time.perf_counter()
    desired_position = payload.desired_position
    resume = payload.resume
    app_user_id = str(payload.app_user_id)
    top_k = 300

    desired_locations = desired_position.get("city") or []
    desired_positions = desired_position.get("positions") or []

    predict_job_titles = desired_position.get("predict_job_titles") or []
    predict_professional_skills = desired_position.get("predict_professional_skills") or []

    skills = resume.get("skills") or []
    work_experiences = resume.get("work_experiences") or []
    educations = resume.get("educations") or []
    major_name_list = [edu["major_name"] for edu in educations if edu.get("major_name")]
    graduate_date = calc_first_degree_graduate_date(educations)

    desired_job_type_list = desired_position.get("job_type") or []
    desired_job_type_list = [job_type for job_type in desired_job_type_list if job_type != "Not sure yet"]

    find_internship_job = "Internship" in desired_job_type_list

    entry_levels = ["Not Applicable", "Entry level"]
    if find_internship_job:
        entry_levels.append("Internship")

    user_post_graduation_work_years = calc_resume_work_years(work_experiences, graduate_date)

    last_work_experience = get_last_work_experience(work_experiences)
    # last_work_experience_description = last_work_experience.get("description") or ""
    last_work_experience_job_title = last_work_experience.get("job") or ""

    if last_work_experience_job_title:
        desired_positions.append(last_work_experience_job_title.strip())

    positions = []
    for desired_position in desired_positions:
        split_desired_positions = desired_position.split("/")
        # "Operations Manager/Director"
        if len(split_desired_positions) == 2 and " " in split_desired_positions[0]:
            base_word = split_desired_positions[0].split(" ")[0]
            split_desired_positions[1] = f"{base_word} {split_desired_positions[1]}"
        for p in split_desired_positions:
            positions.append(p.strip())
    positions = positions + predict_job_titles
    positions = list(set(positions))

    skill_job_dict, responsibility_job_dict, job_dict = {}, {}, {}

    user_locations = await get_user_locations(app_user_id)
    logger.info(
        f"app_user_id:{app_user_id} user_job_type: {desired_job_type_list} positions: {positions} "
        f"user_locations: {user_locations} skills: {skills}"
    )
    if user_locations and (positions or predict_professional_skills):
        basic_recall_job_limit = int(top_k/len(user_locations))
        basic_recall_jobs = await base_recall_jobs_multi_location(
            app_user_id=app_user_id, job_type=desired_job_type_list, titles=positions,
            skills=predict_professional_skills, locations=user_locations,
            user_post_graduation_work_years=user_post_graduation_work_years, find_internship_job=find_internship_job,
            limit=basic_recall_job_limit
        )
        logger.info(f"app_user_id:{app_user_id} base_recall_jobs_multi_location total: {len(basic_recall_jobs)}")
    elif positions or predict_professional_skills:
        titles = positions + predict_professional_skills
        basic_recall_jobs = await base_recall_jobs_exclude_location(
            app_user_id=app_user_id, job_type=desired_job_type_list, titles=titles,
            user_post_graduation_work_years=user_post_graduation_work_years, find_internship_job=find_internship_job,
            limit=top_k
        )
        basic_recall_jobs = sorted(basic_recall_jobs, key=lambda x: x["relevance_score"], reverse=True)
        logger.info(f"app_user_id:{app_user_id} base_recall_jobs_exclude_location total: {len(basic_recall_jobs)}")
    else:
        return []
    recall_job_ids = [str(job["job_id"]) for job in basic_recall_jobs]
    job_dict = {
        str(job["job_id"]): dict(
            title=dict(score=1),
            function=dict(score=1),
            job_type=dict(score=1),
            distance_meters=job.get("distance_meters"),
            relevance_score=job["relevance_score"],
        ) for job in basic_recall_jobs
    }
    if not recall_job_ids:
        return []
    jobs = await get_jobs(recall_job_ids)
    logger.info(f"app_user_id:{app_user_id} get jobs total: {len(jobs)}")
    if not jobs:
        return []
    company_diversity_dict = {}
    match_results, secondary_match_results = [], []
    for job in jobs:
        job_id = str(job["id"])
        title = job["title"]
        company_id = job["company_id"]
        job_skills = job["skills"]
        job_level = job.get("job_level")
        e_job_level = job.get("e_job_level")
        job_level = fix_job_level(job_level, e_job_level)
        if not job.get("responsibilities"):
            continue
        score_detail = job_dict.get(job_id) or {}
        relevance_score = min(float(score_detail.get("relevance_score") or 0)/20, 1)

        skill_match_result = skill_job_dict.get(job_id, {}).get("skill")
        if skill_match_result:
            score_detail["skill"] = skill_match_result
        elif job_skills and skills:
            fix_job_skills = [skill for skill in job_skills if isinstance(skill, str)]
            if not fix_job_skills:
                fix_job_skills = [skill["name"] for skill in job_skills if isinstance(skill, dict)]
            if fix_job_skills:
                skill_score, match_skills = find_matching_skills(skills, fix_job_skills)
                score_detail["skill"] = dict(score=skill_score, match_skills=match_skills)

        experience_match_result = responsibility_job_dict.get(job_id, {}).get("experience")
        if experience_match_result:
            score_detail["experience"] = experience_match_result

        job_work_years = get_job_work_years(job)
        # logger.info(f"app_user_id:{app_user_id} job_work_years: {job_work_years} user_work_years:{user_work_years}")
        if job_work_years:
            yoe_score = calc_work_year_score(job_work_years, user_post_graduation_work_years)
            score_detail["yoe"] = dict(
                score=yoe_score, job_work_years=job_work_years, post_graduation_work_years=user_post_graduation_work_years
            )
            if user_post_graduation_work_years > 1 and yoe_score < 0.6:
                continue
        if not find_internship_job and "intern" in title.lower():
            continue
        if user_post_graduation_work_years <= 0.5:
            if job_level and job_level not in entry_levels:
                continue
            if "new grad" in title.lower():
                score_detail["relevance_score"] = score_detail["relevance_score"] + 10
        # base score
        score_detail["b_score"] = calc_basic_score_by_weight(score_detail)

        score = score_detail["b_score"]
        if user_locations:
            distance_meters = score_detail.get("distance_meters") or None
            work_locations = job.get("work_locations") or []
            work_location_name_list = [wl["name"] for wl in work_locations]
            if distance_meters is not None:
                if distance_meters < 1000:
                    score_detail["location_score"] = 1
                else:
                    score_detail["location_score"] = 0.8
                score = score + score_detail["location_score"]
            elif bool(set(desired_locations) & set(work_location_name_list)):
                score_detail["location_score"] = 1
                score = score + 1
            elif state_match(desired_locations, work_location_name_list):
                score_detail["location_score"] = 0.7
                score = score + 0.7
        job_type = job.get("job_type") or []
        if desired_job_type_list and bool(set(desired_job_type_list) & set(job_type)):
            score_detail["job_type_score"] = 1

        job_majors = job.get("majors") or []
        fix_job_majors = [major for major in job_majors if isinstance(major, str)]
        if not fix_job_majors:
            fix_job_majors = [major["name"] for major in job_majors if isinstance(major, dict)]
        if major_name_list and fix_job_majors and bool(
                set(major.lower() for major in major_name_list) & set(fix_job_majors)
        ):
            score_detail["major_score"] = 1
            score = score + 0.1
        if user_post_graduation_work_years <= 1 and relevance_score < 0.05:
            continue
        elif user_post_graduation_work_years > 1 and relevance_score < 0.1:
            continue
        if score == 0:
            continue
        score = score
        score_detail["score"] = score
        score_detail["reason"] = generate_reasons(score_detail, job)
        job = dict(job_id=job_id, score=max(0, score), detail=score_detail)
        if company_id not in company_diversity_dict:
            company_diversity_dict[company_id] = True
            job["score"] = job["score"] + 2
            match_results.append(job)
        else:
            secondary_match_results.append(job)
    elapsed = time.perf_counter() - start
    total_match_results = match_results + secondary_match_results
    logger.info(f"app_user_id: {app_user_id} match jobs total: {len(total_match_results)} elapsed: {elapsed:.6f}s")
    return total_match_results


if __name__ == '__main__':
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
