"""
MCP Tool: search_runbooks
Semantic search over ChromaDB runbook collection.
"""

import os
import logging
from typing import Any

from fastmcp.tools.tool import Tool

import chromadb
from chromadb.utils import embedding_functions

logger = logging.getLogger("operaiq.tools.runbooks")

CHROMADB_PERSIST_DIR = os.environ.get("CHROMADB_PERSIST_DIR", "./chroma_db")
COLLECTION_NAME = "runbooks"

# Module-level ChromaDB client (persistent storage survives restarts)
_chroma_client = None
_collection = None


def _get_collection():
    global _chroma_client, _collection
    if _collection is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMADB_PERSIST_DIR)
        embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
        _collection = _chroma_client.get_or_create_collection(
            name=COLLECTION_NAME,
            embedding_function=embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection


def _add_tool_with_param_descriptions(
    mcp,
    fn,
    description: str,
    param_descriptions: dict[str, str],
) -> None:
    tool = Tool.from_function(fn, description=description)
    properties = tool.parameters.get("properties", {})
    for name, desc in param_descriptions.items():
        if name in properties:
            properties[name]["description"] = desc
    mcp.add_tool(tool)


def register_runbook_tools(mcp) -> None:

    async def search_runbooks(
        query: str,
        top_k: int = 3,
    ) -> list[dict[str, Any]]:
        """
        Semantic search over ChromaDB runbook collection.

        Args:
            query: Natural language search query.
            top_k: Number of top results to return (max 10).

        Returns:
            List of {id, service, title, content_snippet, similarity_score} dicts.
        """
        if top_k < 1 or top_k > 10:
            raise ValueError("top_k must be between 1 and 10")

        collection = _get_collection()

        try:
            results = collection.query(
                query_texts=[query],
                n_results=min(top_k, collection.count()),
                include=["documents", "metadatas", "distances"],
            )
        except Exception as exc:
            logger.error(f"search_runbooks ChromaDB query failed: {exc}")
            raise RuntimeError(f"Runbook search failed: {exc}") from exc

        if not results or not results["ids"]:
            return []

        output = []
        ids = results["ids"][0]
        docs = results["documents"][0]
        metas = results["metadatas"][0]
        distances = results["distances"][0]

        for rb_id, doc, meta, dist in zip(ids, docs, metas, distances):
            # Convert cosine distance to similarity (0–1, higher is better)
            similarity = round(1 - dist, 4)
            # Truncate content to first 500 chars for the snippet
            snippet = doc[:500].strip() + ("..." if len(doc) > 500 else "")
            output.append(
                {
                    "id": rb_id,
                    "service": meta.get("service", "unknown"),
                    "title": meta.get("title", "Untitled"),
                    "content_snippet": snippet,
                    "full_content": doc,
                    "similarity_score": similarity,
                    "last_updated": meta.get("last_updated", ""),
                }
            )

        return output

    _add_tool_with_param_descriptions(
        mcp,
        search_runbooks,
        description=(
            "Searches the OperaIQ runbook knowledge base using semantic similarity. "
            "Given a natural language query (e.g., 'payments service high error rate'), "
            "returns the most relevant runbook sections with similarity scores. "
            "Use this to find operational procedures and troubleshooting steps."
        ),
        param_descriptions={
            "query": "Natural language query used for semantic runbook search.",
            "top_k": "Number of results to return (1-10).",
        },
    )
