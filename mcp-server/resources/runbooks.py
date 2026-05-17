"""
OperaIQ MCP Resource: resource://runbooks/{service}

Returns all runbook documents for a given service from ChromaDB as plain text.
"""

from fastmcp import FastMCP
from chromadb import PersistentClient
import os
import logging

logger = logging.getLogger("operaiq.resources.runbooks")

CHROMADB_DIR = os.environ.get("CHROMADB_PERSIST_DIR", "./chroma_db")


def register_runbook_resources(mcp: FastMCP) -> None:
    """Register the resource://runbooks/{service} resource."""

    @mcp.resource("resource://runbooks/{service}")
    async def get_runbooks_for_service(service: str) -> str:
        """
        Returns all runbook documents for a specific service as plain text.
        Useful for agents that need full runbook context for a given service.
        """
        try:
            client = PersistentClient(path=CHROMADB_DIR)
            collection = client.get_or_create_collection("runbooks")

            results = collection.get(
                where={"service": service},
                include=["documents", "metadatas"],
            )

            docs = results.get("documents") or []
            metas = results.get("metadatas") or []

            if not docs:
                return f"No runbooks found for service: {service}"

            lines = []
            for i, (doc, meta) in enumerate(zip(docs, metas)):
                title = meta.get("title", f"Runbook {i + 1}") if meta else f"Runbook {i + 1}"
                last_updated = meta.get("last_updated", "unknown") if meta else "unknown"
                lines.append(f"## {title}")
                lines.append(f"_Last updated: {last_updated}_")
                lines.append("")
                lines.append(doc or "")
                lines.append("")
                lines.append("---")
                lines.append("")

            return "\n".join(lines)

        except Exception as exc:
            logger.error(f"Failed to fetch runbooks for service '{service}': {exc}")
            return f"Error fetching runbooks for service '{service}': {exc}"
