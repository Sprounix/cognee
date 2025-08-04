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


async def process_single_job(job):
    """
    Process a single job asynchronously.
    
    Args:
        job: Dictionary containing job data
        
    Returns:
        tuple: (job_id, success, result_or_error)
    """
    job_id = job.pop("new_id", None)
    if not job_id:
        return None, False, "No job_id found"
    
    job["id"] = job_id
    
    # Clean up job data
    if job.get("job_function") and job.get("job_function").lower() == "other":
        job.pop("job_function", None)
    if job.get("job_level") and job.get("job_level").lower() == "not applicable":
        job.pop("job_level", None)
    
    job_str = json.dumps(job, ensure_ascii=False)
    
    try:
        start_time = time.time()
        dataset_name = f"{job_id}"
        
        # Add job to cognee
        add_result = await cognee.add(job_str, dataset_name=dataset_name, node_set=["job"])
        print(f"{dataset_name} add_result: {add_result}")
        
        # Cognify the job
        cognify_result = await cognee.cognify(
            datasets=dataset_name,
            graph_model=Job,
            chunker=TextChunker,
        )
        
        end_time = time.time()
        processing_time = end_time - start_time
        print(f"{dataset_name} cognify_result: {cognify_result}, cost: {processing_time}")
        
        return job_id, True, {
            "add_result": add_result,
            "cognify_result": cognify_result,
            "processing_time": processing_time
        }
        
    except Exception as e:
        error_msg = f"Error processing job_id: {job_id}, error: {e}"
        print(error_msg)
        return job_id, False, str(e)


async def add_and_cognify_from_csv(file_path, prune=False, limit=(0, 10), max_concurrent=5):
    """
    Process jobs from CSV file concurrently using asyncio.gather.
    
    Args:
        file_path: Path to the CSV file
        prune: Whether to clean all data before processing
        limit: Tuple of (start_index, end_index) for processing subset
        max_concurrent: Maximum number of concurrent tasks (default: 5)
    """
    if prune:
        await clearn_all_data()
        return
    
    # Read and prepare jobs
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        jobs = [{key: value for key, value in row.items() if key in [
            "job_function", "new_id", "title", "description", "job_type", "job_level"
        ]} for row in reader]
    
    if not jobs:
        print("No jobs found in CSV file")
        return
    
    # Apply limit
    jobs = jobs[limit[0]: limit[1]]
    print(f"Processing {len(jobs)} jobs concurrently (max {max_concurrent} at a time)")
    
    # Process jobs in batches to control concurrency
    results = []
    for i in range(0, len(jobs), max_concurrent):
        batch = jobs[i:i + max_concurrent]
        
        # Create tasks for the current batch
        tasks = [process_single_job(job) for job in batch]
        
        # Execute batch concurrently
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process results
        for result in batch_results:
            if isinstance(result, Exception):
                print(f"Task failed with exception: {result}")
                results.append((None, False, str(result)))
            else:
                results.append(result)
        
        print(f"Completed batch {i//max_concurrent + 1}/{(len(jobs) + max_concurrent - 1)//max_concurrent}")
    
    # Summary
    successful = sum(1 for _, success, _ in results if success)
    failed = len(results) - successful
    print(f"\nProcessing complete: {successful} successful, {failed} failed")


if __name__ == "__main__":
    base_dir = os.path.dirname(__file__)
    csv_file = os.path.join(base_dir, "../../data", "jobs1000_new.csv")
    asyncio.run(
        add_and_cognify_from_csv(csv_file, prune=False, limit=(0, 1))
    )
