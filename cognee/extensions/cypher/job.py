from typing import List, Dict

from cognee.infrastructure.databases.graph import get_graph_engine


async def query(cypher):
    graph_engine = await get_graph_engine()
    results = await graph_engine.query(cypher)
    return results


async def get_job_ids_by_skills(skill_ids) -> List[str]:
    cypher = f"MATCH (job:Job)-[r:skills]->(skill:JobSkill) WHERE skill.id IN {skill_ids} RETURN collect(DISTINCT job.id) AS job_ids"
    results = await query(cypher)
    return results[0]["job_ids"] if results else []


async def get_job_ids_by_job_function(job_function_ids) -> List[str]:
    cypher = f"MATCH (job:Job)-[r:job_function]->(fun:JobFunction) WHERE fun.id IN {job_function_ids} RETURN collect(DISTINCT job.id) AS job_ids"
    results = await query(cypher)
    return results[0]["job_ids"] if results else []


async def get_job_ids_by_responsibility(responsibility_ids) -> List[str]:
    cypher = f"MATCH (job:Job)-[r:responsibilities]->(res:ResponsibilityItem) WHERE res.id IN {responsibility_ids} RETURN collect(DISTINCT job.id) AS job_ids"
    results = await query(cypher)
    return results[0]["job_ids"] if results else []


async def get_job_skill_ids(job_ids) -> List[Dict]:
    cypher = f"MATCH(job:Job)-[r:skills]->(skill:JobSkill) WHERE job.id IN {job_ids} RETURN collect(DISTINCT skill.id) AS skills, job.id AS job_id"
    results = await query(cypher)
    return results


async def get_job_responsibility_ids(job_ids) -> List[Dict]:
    cypher = f"MATCH(job:Job)-[r:responsibilities]->(res:ResponsibilityItem) WHERE job.id IN {job_ids} RETURN collect(DISTINCT res.id) AS responsibility_ids, job.id AS job_id"
    results = await query(cypher)
    return results


async def get_jobs(job_ids) -> List[Dict]:
    cypher = f"""
    MATCH (job:Job)
    WHERE job.id in {job_ids}""" + """
    
    OPTIONAL MATCH (job)-[:job_function]->(func:JobFunction)
    OPTIONAL MATCH (job)-[:work_locations]->(loc:JobLocation)
    OPTIONAL MATCH (job)-[:skills]->(skill:JobSkill)
    OPTIONAL MATCH (job)-[:qualification]->(:Qualification)-[:required]->(reqItem:QualificationItem)
    OPTIONAL MATCH (job)-[:qualification]->(:Qualification)-[:preferred]->(prefItem:QualificationItem)
    OPTIONAL MATCH (job)-[:responsibilities]->(resp:ResponsibilityItem)
    OPTIONAL MATCH (job)-[:majors]->(major:JobMajor)
    
    WITH job,
         COLLECT(DISTINCT CASE WHEN func.id IS NOT NULL THEN {id: func.id, name: func.name} END) AS funcs,
         COLLECT(DISTINCT CASE WHEN loc.id IS NOT NULL THEN {id: loc.id, name: loc.name} END) AS locs,
         COLLECT(DISTINCT CASE WHEN skill.id IS NOT NULL THEN {id: skill.id, name: skill.name} END) AS skills,
         COLLECT(DISTINCT CASE WHEN reqItem.id IS NOT NULL THEN {id: reqItem.id, category: reqItem.category, item: reqItem.item} END) AS required,
         COLLECT(DISTINCT CASE WHEN prefItem.id IS NOT NULL THEN {id: prefItem.id, category: prefItem.category, item: prefItem.item} END) AS preferred,
         COLLECT(DISTINCT CASE WHEN resp.id IS NOT NULL THEN {id: resp.id, item: resp.item} END) AS responsibilities,
         COLLECT(DISTINCT CASE WHEN major.id IS NOT NULL THEN {id: major.id, name: major.name} END) AS majors

    RETURN {
      id: job.id,
      title: job.title,
      job_function: funcs,
      job_level: job.job_level,
      work_locations: locs,
      skills: skills,
      job_type: job.job_type,
      majors: majors,
      qualification: {
        required: required,
        preferred: preferred
      },
      responsibilities: responsibilities
    } AS job_json
    """
    results = await query(cypher)
    return [r["job_json"] for r in results]
