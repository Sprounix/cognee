import asyncio

import cognee
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.shared.logging_utils import get_logger

logger = get_logger("clean")


async def clearn_all_data():
    # nest_asyncio.apply()
    print("Deleting all files and data...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=False)
    print("All files deleted.")


async def delete_job_data(job_id):
    pg_db = get_relational_engine()
    graph_db = await get_graph_engine()
    # 1. 查找 datasets 表中 name=program_id 的 dataset_id
    datasets = await pg_db.execute_query(f"SELECT id FROM datasets WHERE name = '{job_id}'")
    if not datasets:
        return

    logger.info(f"Job {job_id} and related data delete start.")
    dataset_id = str(datasets[0]['id'])  # Access tuple by index

    # 2. 查找 dataset_data 表中 dataset_id 对应的 data_id
    dataset_data = await pg_db.execute_query(f"SELECT data_id FROM dataset_data WHERE dataset_id = '{dataset_id}'")

    if not dataset_data:
        logger.warning(f"No data_id found for dataset_id {dataset_id}")
        return
    data_ids = [row['data_id'] for row in dataset_data]  # Access tuple by index

    # 3. 删除 dataset_data、data 表中对应记录
    await pg_db.execute(f"DELETE FROM dataset_data WHERE dataset_id = '{dataset_id}'")
    for data_id in data_ids:
        await pg_db.execute(f"DELETE FROM data WHERE id = '{data_id}'")

    # 4. Neo4j 相关节点和关系删除
    # 通过 data_id 查找 TextDocument 节点
    for data_id in data_ids:
        # 查找 TextDocument 节点
        docs = await graph_db.query(
            "MATCH (n:TextDocument {id: $data_id}) RETURN n.id AS id",
            {"data_id": str(data_id)}
        )
        if not docs:
            continue
        text_doc_id = docs[0]["id"]

        # 递归查找所有下游节点
        cypher = """
        MATCH (doc:TextDocument {id: $doc_id})
        OPTIONAL MATCH (doc)-[*0..4]-(n)
        RETURN n.type, n.id
        """
        result = await graph_db.query(cypher, {"doc_id": text_doc_id})
        # result 是一个 list，list 的每个元素是 dict，去重
        seen = set()
        unique_result = []
        for item in result:
            # 将 dict 转为 tuple 以便 hash
            t = tuple(sorted(item.items()))
            if t not in seen:
                seen.add(t)
            unique_result.append(item)
        result = unique_result

        if not result:
            continue

        for item in result:
            table = item['n.type']
            node_id = item['n.id']

            if table == "Job":
                await pg_db.execute(
                    f"""DELETE FROM "Job_title" WHERE id = '{node_id}'"""
                )
            if table == "JobSkill":
                await pg_db.execute(
                    f"""DELETE FROM "JobSkill_name" WHERE id = '{node_id}'"""
                )
            if table == "JobMajor":
                await pg_db.execute(
                    f"""DELETE FROM "JobMajor_name" WHERE id = '{node_id}'"""
                )
            if table == "JobLocation":
                await pg_db.execute(
                    f"""DELETE FROM "JobLocation_name" WHERE id = '{node_id}'"""
                )
            if table == "JobFunction":
                await pg_db.execute(
                    f"""DELETE FROM "JobFunction_name" WHERE id = '{node_id}'"""
                )
            if table == "QualificationItem":
                await pg_db.execute(
                    f"""DELETE FROM "QualificationItem_item" WHERE id = '{node_id}'"""
                )
            if table == "ResponsibilityItem":
                await pg_db.execute(
                    f"""DELETE FROM "ResponsibilityItem_item" WHERE id = '{node_id}'"""
                )
            if table == "DocumentChunk":
                await pg_db.execute(
                    f"""DELETE FROM "DocumentChunk_text" WHERE id = '{node_id}'"""
                )
            if table == "TextDocument":
                await pg_db.execute(
                    f"""DELETE FROM "TextDocument_name" WHERE id = '{node_id}'"""
                )
            if table == "TextSummary":
                await pg_db.execute(
                    f"""DELETE FROM "TextSummary" WHERE id = '{node_id}'"""
                )

        node_ids = [item['n.id'] for item in result]
        # 删除所有相关节点
        if node_ids:
            await graph_db.delete_nodes(node_ids)

        # 7. 删除 graph_relationship_ledger 相关边记录
        # 通过 node_ids 删除相关边
        ids_str = ",".join([f"'{nid}'" for nid in node_ids])
        await pg_db.execute(
            f"DELETE FROM graph_relationship_ledger WHERE source_node_id IN ({ids_str}) OR destination_node_id IN ({ids_str})"
        )

    # 8. 删除 datasets 表中的记录
    await pg_db.execute(
        f"""DELETE FROM datasets WHERE id = '{dataset_id}'"""
    )

    logger.info(f"Job {job_id} and related data deleted.")


if __name__ == "__main__":
    asyncio.run(
        # delete_job_data("c43f9992-f0b3-4506-943d-4582694b143f")
        clearn_all_data()
    )
