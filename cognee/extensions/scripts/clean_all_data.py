import asyncio

import cognee
from cognee.api.v1.visualize.visualize import visualize_graph
from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.databases.vector.embeddings import get_embedding_engine
from cognee.infrastructure.databases.relational import get_relational_engine
from cognee.shared.logging_utils import get_logger


logger = get_logger("")


async def clearn_all_data():
    # nest_asyncio.apply()
    print("Deleting all files and data...")
    await cognee.prune.prune_data()
    await cognee.prune.prune_system(metadata=False)
    print("All files deleted.")


async def delete_job_data(job_id):
    """
    删除一个program。每个program有一个对应的dataset_name,也就是输入参数program_id，
    首先从datasets中根据dataset_name找到对应的dataset_id，
    在从dataset_data表里面查询到对应的data_id,
    然后根据data_id 从Document_name表中删除对应的document；
    根据data_id 从neo4j中查询到对应的TextDocument节点，
    通过TextDocument节点id，可以查询出来所有的DocumentChunk节点和TextSummary节点，
    通过DocumentChunk节点，可以查询对应InternationalExchangeProgram节点，
    通过InternationalExchangeProgram节点，可以查询出所有的Language,Institution,Subject节点，
    删除上面所提到的节点及对应的边，并且记录下这些节点的id。
    通过InternationalExchangeProgram节点id，在pg中删除InternationalExchangeProgram_description、InternationalExchangeProgram_name、InternationalExchangeProgram_program_type中的内容
    通过Language的节点id，删除Language_name中的内容
    通过Institution节点id, 删除Institution_name，Institution_locaitonCity，Institution_locationCountry中的内容
    通过Subject的节点id，删除Subject_name中的内容
    通过TextDocument节点id，删除TextDocument_text中的内容
    通过TextSummary节点id，删除TextSummary_text中的内容
    通过DocumentChunk节点id，删除DocumentChunk_text中的内容
    通过上述的neo4j节点id，删除graph_relationship_ledger中的边的记录。
    删除data, dataset_data中对应的记录。
    """
    pg_db = get_relational_engine()
    graph_db = await get_graph_engine()
    # 1. 查找 datasets 表中 name=program_id 的 dataset_id
    datasets = await pg_db.execute_query(f"SELECT id FROM datasets WHERE name = '{job_id}'")
    if not datasets:
        logger.warning(f"Job {job_id} not found in datasets.")
        return False
    dataset_id = datasets[0]['id']  # Access tuple by index

    # 2. 查找 dataset_data 表中 dataset_id 对应的 data_id
    dataset_data = await pg_db.execute_query(f"SELECT data_id FROM dataset_data WHERE dataset_id = '{dataset_id}'")
    if not dataset_data:
        logger.warning(f"No data_id found for dataset_id {dataset_id}")
        return False
    data_ids = [row['data_id'] for row in dataset_data]  # Access tuple by index

    # 3. 删除 dataset_data、data 表中对应记录
    await pg_db.execute_query(f"DELETE FROM dataset_data WHERE dataset_id = '{dataset_id}'")
    for data_id in data_ids:
        await pg_db.execute_query(f"DELETE FROM data WHERE id = '{data_id}'")

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

        # 查找所有相关节点（DocumentChunk, TextSummary, InternationalExchangeProgram, Language, Institution, Subject）
        # 递归查找所有下游节点
        cypher = """
        MATCH (doc:TextDocument {id: $doc_id})
        OPTIONAL MATCH (doc)-[*0..3]-(n)
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
        node_ids = [item['n.id'] for item in result]

        for item in result:
            table = item['n.type']
            node_id = item['n.id']

            if table == "Job":
                # 删除 InternationalExchangeProgram_description、InternationalExchangeProgram_name、InternationalExchangeProgram_program_type
                await pg_db.execute_query(
                    f'DELETE FROM "InternationalExchangeProgram_description" WHERE payload->>\'id\' = \'{node_id}\'')
                await pg_db.execute_query(
                    f'DELETE FROM "InternationalExchangeProgram_name" WHERE payload->>\'id\' = \'{node_id}\'')
                await pg_db.execute_query(
                    f'DELETE FROM "InternationalExchangeProgram_program_type" WHERE payload->>\'id\' = \'{node_id}\'')
            if table == "Language":
                # 删除 Language_name
                await pg_db.execute_query(f'DELETE FROM "Language_name" WHERE payload->>\'id\' = \'{node_id}\'')
            if table == "Institution":
                # 删除 Institution_name, Institution_locationCity, Institution_locationCountry
                await pg_db.execute_query(f'DELETE FROM "Institution_name" WHERE payload->>\'id\' = \'{node_id}\'')
                await pg_db.execute_query(
                    f'DELETE FROM "Institution_locationCity" WHERE payload->>\'id\' = \'{node_id}\'')
                await pg_db.execute_query(
                    f'DELETE FROM "Institution_locationCountry" WHERE payload->>\'id\' = \'{node_id}\'')
            if table == "Subject":
                # 删除 Subject_name
                await pg_db.execute_query(f'DELETE FROM "Subject_name" WHERE payload->>\'id\' = \'{node_id}\'')
            if table == "TextDocument":
                # 删除 TextDocument_name
                await pg_db.execute_query(f'DELETE FROM "TextDocument_name" WHERE payload->>\'id\' = \'{node_id}\'')
            if table == "TextSummary":
                # 删除 TextSummary_text
                await pg_db.execute_query(f'DELETE FROM "TextSummary_text" WHERE payload->>\'id\' = \'{node_id}\'')
            if table == "DocumentChunk":
                # 删除 DocumentChunk_text
                await pg_db.execute_query(f'DELETE FROM "DocumentChunk_text" WHERE payload->>\'id\' = \'{node_id}\'')
        # 删除所有相关节点
        if node_ids:
            await graph_db.delete_nodes(node_ids)

        # 7. 删除 graph_relationship_ledger 相关边记录
        # 通过 node_ids 删除相关边
        ids_str = ",".join([f"'{nid}'" for nid in node_ids])
        await pg_db.execute_query(
            f"DELETE FROM graph_relationship_ledger WHERE source_node_id IN ({ids_str}) OR destination_node_id IN ({ids_str})"
        )
    # 8. 删除 datasets 表中的记录
    await pg_db.execute_query(f"DELETE FROM datasets WHERE id = '{dataset_id}'")

    logger.info(f"Job {job_id} and related data deleted.")
    return True

if __name__ == "__main__":
    asyncio.run(
        clearn_all_data()
    )
