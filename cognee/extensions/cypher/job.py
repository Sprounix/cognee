from typing import List, Dict

from cognee.infrastructure.databases.graph import get_graph_engine


async def query(cypher):
    graph_engine = await get_graph_engine()
    results = await graph_engine.query(cypher)
    return results


async def get_job_ids_by_skills(skill_ids) -> List[str]:
    cypher = f"MATCH (Job:Job)-[r:skills]->(skill:JobSkill) WHERE skill.id IN {skill_ids} RETURN collect(DISTINCT Job.id) AS job_ids"
    results = await query(cypher)
    return results[0]["job_ids"] if results else []


async def get_job_skill_ids(job_ids) -> List[Dict]:
    cypher = f"MATCH(Job:Job)-[r:skills]->(skill:JobSkill) WHERE Job.id IN {job_ids} RETURN collect(DISTINCT skill.id) AS skills, Job.id AS job_id"
    results = await query(cypher)
    return results


async def get_jobs(job_ids) -> List[Dict]:
    cypher = f"""MATCH (job:Job)
    WHERE job.id in {job_ids}""" + """
    
    OPTIONAL MATCH (job)-[:job_function]->(func:JobFunction)
    OPTIONAL MATCH (job)-[:work_locations]->(loc:JobLocation)
    OPTIONAL MATCH (job)-[:skills]->(skill:JobSkill)
    OPTIONAL MATCH (job)-[:qualification]->(qua: Qualification)-[:required]->(reqItem:QualificationItem)
    OPTIONAL MATCH (job)-[:qualification]->(qua: Qualification)-[:preferred]->(prefItem:QualificationItem)
    OPTIONAL MATCH (job)-[:responsibilities]->(resp:ResponsibilityItem)
    OPTIONAL MATCH (job)-[:majors]->(major:JobMajor) WHERE (major.name IS NOT NULL) 
    
    WITH 
      job,
      COLLECT(DISTINCT {id: func.id, name: func.name}) AS job_function,
      COLLECT(DISTINCT {id: loc.id, name: loc.name}) AS work_locations,
      COLLECT(DISTINCT {id: skill.id, name: skill.name}) AS skills,
      COLLECT(DISTINCT {id: reqItem.id, category: reqItem.category, item: reqItem.item}) AS required,
      COLLECT(DISTINCT {id: prefItem.id, category: prefItem.category, item: prefItem.item}) AS preferred,
      COLLECT(DISTINCT {id: resp.id, item: resp.item}) AS responsibilities,
      COLLECT(DISTINCT {id: major.id, name: major.name}) AS majors

    RETURN {
      id: job.id,
      title: job.title,
      job_function: job_function,
      job_level: job.job_level,  
      work_locations: work_locations,
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
