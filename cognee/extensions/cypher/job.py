import asyncio
from typing import List, Dict

from cognee.infrastructure.databases.graph import get_graph_engine


async def get_jobs(job_ids) -> List[Dict]:
    graph_engine = await get_graph_engine()

    cypher = f"""MATCH (job:Job)
    WHERE job.id in {job_ids}""" + """
    
    OPTIONAL MATCH (job)-[:work_locations]->(loc:JobLocation)
    OPTIONAL MATCH (job)-[:skills]->(skill:JobSkill)
    OPTIONAL MATCH (job)-[:qualification]->(qua: Qualification)-[:required]->(reqItem:QualificationItem)
    OPTIONAL MATCH (job)-[:qualification]->(qua: Qualification)-[:preferred]->(prefItem:QualificationItem)
    OPTIONAL MATCH (job)-[:responsibilities]->(resp:ResponsibilityItem)
    OPTIONAL MATCH (job)-[:majors]->(major:JobMajor) WHERE (major.name IS NOT NULL) 
    
    WITH 
      job,
      COLLECT(DISTINCT {id: loc.id, name: loc.name}) AS work_locations,
      COLLECT(DISTINCT {id: skill.id, name: skill.name}) AS skills,
      COLLECT(DISTINCT {id: reqItem.id, category: reqItem.category, item: reqItem.item}) AS required,
      COLLECT(DISTINCT {id: prefItem.id, category: prefItem.category, item: prefItem.item}) AS preferred,
      COLLECT(DISTINCT {id: resp.id, item: resp.item}) AS responsibilities,
      COLLECT(DISTINCT {id: major.id, name: major.name}) AS majors      

    RETURN {
      id: job.id,
      title: job.title,
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
    results = await graph_engine.query(cypher)
    return [r["job_json"] for r in results]


if __name__ == "__main__":
    find_job_ids = ["fb9dc111-ae97-40d8-9ae2-5265ebb4173c", "4b5fb349-02a5-43ed-a51f-4b4c5358b632"]
    results = asyncio.run(get_jobs(find_job_ids))
    print("xxx"*10)
    import json
    for job in results:
        print(json.dumps(job, ensure_ascii=False, indent=2))
