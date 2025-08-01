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


async def get_responsibility_items(responsibility_ids) -> List[str]:
    cypher = f"MATCH(r:ResponsibilityItem) WHERE r.id IN {responsibility_ids} "+"RETURN {id: r.id, item: r.item} AS responsibilities"
    results = await query(cypher)
    # [{"id": "", "item": ""}, ]
    return [r["responsibilities"] for r in results]


async def get_jobs(job_ids) -> List[Dict]:
    cypher = f"""
    MATCH (job:Job)
    WHERE job.id in {job_ids}""" + """
    
    RETURN {
      id: job.id,
      title: job.title,
      job_function: [(job)-[:job_function]->(func:JobFunction) | {id: func.id, name: func.name}],
      job_level: job.job_level,
      work_locations: [(job)-[:work_locations]->(loc:JobLocation) | {id: loc.id, name: loc.name}],
      skills: [(job)-[:skills]->(skill:JobSkill) | {id: skill.id, name: skill.name}],
      job_type: job.job_type,
      majors: [(job)-[:majors]->(major:JobMajor) | {id: major.id, name: major.name}],
      qualification: {
        required: [(job)-[:qualification]->(:Qualification)-[:required]->(reqItem:QualificationItem) | 
                  {id: reqItem.id, category: reqItem.category, item: reqItem.item}],
        preferred: [(job)-[:qualification]->(:Qualification)-[:preferred]->(prefItem:QualificationItem) | 
                   {id: prefItem.id, category: prefItem.category, item: prefItem.item}]
      },
      responsibilities: [(job)-[:responsibilities]->(resp:ResponsibilityItem) | 
                       {id: resp.id, item: resp.item}]
    } AS job_json
    """
    results = await query(cypher)
    return [r["job_json"] for r in results]
