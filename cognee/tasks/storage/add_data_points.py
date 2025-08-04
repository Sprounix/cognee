import asyncio
from typing import List

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.infrastructure.engine import DataPoint
from cognee.modules.graph.utils import deduplicate_nodes_and_edges, get_graph_from_model
from cognee.shared.logging_utils import get_logger
from .index_data_points import index_data_points
from .index_graph_edges import index_graph_edges

logger = get_logger("data_point")


async def add_data_points(data_points: List[DataPoint]) -> List[DataPoint]:
    nodes = []
    edges = []

    added_nodes = {}
    added_edges = {}
    visited_properties = {}

    logger.info("add_data_points total:", len(data_points))

    results = await asyncio.gather(
        *[
            get_graph_from_model(
                data_point,
                added_nodes=added_nodes,
                added_edges=added_edges,
                visited_properties=visited_properties,
            )
            for data_point in data_points
        ]
    )

    logger.info("add_data_points get_graph_from_model total:", len(results))

    for result_nodes, result_edges in results:
        nodes.extend(result_nodes)
        edges.extend(result_edges)

    nodes, edges = deduplicate_nodes_and_edges(nodes, edges)

    logger.info(f"add_data_points deduplicate_nodes_and_edges nodes: {len(nodes)} edges: {len(edges)}")

    graph_engine = await get_graph_engine()

    await index_data_points(nodes)

    logger.info(f"add_data_points index_data_points")

    await graph_engine.add_nodes(nodes)

    logger.info(f"add_data_points add_nodes")
    await graph_engine.add_edges(edges)

    logger.info(f"add_data_points add_edges")

    # This step has to happen after adding nodes and edges because we query the graph.
    await index_graph_edges()

    logger.info(f"add_data_points index_graph_edges")

    return data_points
