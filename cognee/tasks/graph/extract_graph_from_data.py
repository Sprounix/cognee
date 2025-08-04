import asyncio
from typing import Type, List, Optional

from pydantic import BaseModel

from cognee.infrastructure.databases.graph import get_graph_engine
from cognee.modules.ontology.rdf_xml.OntologyResolver import OntologyResolver
from cognee.modules.chunking.models.DocumentChunk import DocumentChunk
from cognee.modules.data.extraction.knowledge_graph import extract_content_graph
from cognee.modules.graph.utils import (
    expand_with_nodes_and_edges,
    retrieve_existing_edges,
)
from cognee.shared.data_models import KnowledgeGraph
from cognee.tasks.storage import add_data_points
from cognee.shared.logging_utils import get_logger


logger = get_logger("graph")


async def integrate_chunk_graphs(
    data_chunks: list[DocumentChunk],
    chunk_graphs: list,
    graph_model: Type[BaseModel],
    ontology_adapter: OntologyResolver,
) -> List[DocumentChunk]:
    """Updates DocumentChunk objects, integrates data points and edges into databases."""
    graph_engine = await get_graph_engine()
    logger.info("integrate_chunk_graphs start, is KnowledgeGraph:", graph_model is not KnowledgeGraph)

    if graph_model is not KnowledgeGraph:
        for chunk_index, chunk_graph in enumerate(chunk_graphs):
            data_chunks[chunk_index].contains = chunk_graph

        await add_data_points(chunk_graphs)
        return data_chunks

    logger.info("integrate_chunk_graphs add_data_points")

    existing_edges_map = await retrieve_existing_edges(
        data_chunks,
        chunk_graphs,
        graph_engine,
    )
    logger.info("integrate_chunk_graphs retrieve_existing_edges")

    graph_nodes, graph_edges = expand_with_nodes_and_edges(
        data_chunks, chunk_graphs, ontology_adapter, existing_edges_map
    )

    logger.info("integrate_chunk_graphs expand_with_nodes_and_edges")

    if len(graph_nodes) > 0:
        await add_data_points(graph_nodes)

    logger.info("integrate_chunk_graphs add_data_points")

    if len(graph_edges) > 0:
        await graph_engine.add_edges(graph_edges)

    logger.info("integrate_chunk_graphs add_edges")
    return data_chunks


async def extract_graph_from_data(
    data_chunks: List[DocumentChunk],
    graph_model: Type[BaseModel],
    ontology_adapter: OntologyResolver = None,
) -> List[DocumentChunk]:
    """
    Extracts and integrates a knowledge graph from the text content of document chunks using a specified graph model.
    """
    chunk_graphs = await asyncio.gather(
        *[extract_content_graph(chunk.text, graph_model) for chunk in data_chunks]
    )

    # Note: Filter edges with missing source or target nodes
    if graph_model == KnowledgeGraph:
        for graph in chunk_graphs:
            valid_node_ids = {node.id for node in graph.nodes}
            graph.edges = [
                edge
                for edge in graph.edges
                if edge.source_node_id in valid_node_ids and edge.target_node_id in valid_node_ids
            ]

    return await integrate_chunk_graphs(
        data_chunks, chunk_graphs, graph_model, ontology_adapter or OntologyResolver()
    )
