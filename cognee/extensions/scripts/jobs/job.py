import asyncio
import csv
import json
import os
import time
import cognee
from cognee.extensions.schemas.job import Job
from cognee.infrastructure.llm.config import get_llm_config


async def clearn_all_data():
    # nest_asyncio.apply()
    print("Deleting all files and data...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    print("All files deleted.")


async def add_and_cognify_from_csv(file_path, prune=False, limit=1):
    if prune:
        await clearn_all_data()
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        jobs = [{key: value for key, value in row.items() if key in ["id", "title", "description"]} for row in reader]
    if not jobs:
        print("not exist jobs")
        return
    jobs = jobs[51:60]
    for job in jobs:
        job_id = job.pop("id", None)
        if not job_id:
            continue
        job_str = json.dumps(job, ensure_ascii=False)
        try:
            start_time = time.time()
            dataset_name = f"{job_id}"
            add_result = await cognee.add(job_str, dataset_name=dataset_name, node_set=["job"])
            print(f"{dataset_name} add_result: {add_result}")
            cognify_result = await cognee.cognify(
                datasets=dataset_name,
                graph_model=Job,
                chunk_size=5000
            )
            end_time = time.time()
            print(f"{dataset_name} cognify_result: {cognify_result}, cost: {end_time-start_time}")
        except Exception as e:
            print(f"Error processing job_id: {job_id}, error: {e}")
            continue


if __name__ == "__main__":
    config = get_llm_config()
    base_dir = os.path.dirname(__file__)
    graph_prompt_path = os.path.join(base_dir, "../../prompts", "job-extraction.txt")
    print("graph_prompt_path:", graph_prompt_path)

    # config.graph_prompt_path = graph_prompt_path

    csv_file = os.path.join(base_dir, "../../data", "jobs1000.csv")
    asyncio.run(
        add_and_cognify_from_csv(csv_file, prune=False, limit=10)
    )
