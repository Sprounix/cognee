import asyncio
import csv
import json
import os
import time

import cognee
from cognee.extensions.schemas.job import Job
from cognee.extensions.chunking.TextChunker import TextChunker

async def clearn_all_data():
    # nest_asyncio.apply()
    print("Deleting all files and data...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=True)
    print("All files deleted.")


async def add_and_cognify_from_csv(file_path, prune=False, limit=(0, 10)):
    if prune:
        await clearn_all_data()
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        jobs = [{key: value for key, value in row.items() if key in ["new_id", "title", "description"]} for row in reader]
    if not jobs:
        print("not exist jobs")
        return
    jobs = jobs[:30]
    for job in jobs:
        job_id = job.pop("new_id", None)
        if not job_id:
            continue
        job["id"] = job_id
        job_str = json.dumps(job, ensure_ascii=False)
        try:
            start_time = time.time()
            dataset_name = f"{job_id}"
            add_result = await cognee.add(job_str, dataset_name=dataset_name, node_set=["job"])
            print(f"{dataset_name} add_result: {add_result}")
            cognify_result = await cognee.cognify(
                datasets=dataset_name,
                graph_model=Job,
                chunker=TextChunker,
            )
            end_time = time.time()
            print(f"{dataset_name} cognify_result: {cognify_result}, cost: {end_time-start_time}")
        except Exception as e:
            print(f"Error processing job_id: {job_id}, error: {e}")
            continue


if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    csv_file = os.path.join(base_dir, "../../data", "jobs1000_new.csv")
    asyncio.run(
        add_and_cognify_from_csv(csv_file, prune=True, limit=(0, 10))
    )
