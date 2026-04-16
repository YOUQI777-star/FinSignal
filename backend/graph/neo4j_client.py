from __future__ import annotations


class Neo4jClient:
    """Placeholder for future Neo4j AuraDB integration."""

    def get_company_graph(self, market: str, code: str) -> dict:
        company_id = f"{market}:{code}"
        return {
            "company_id": company_id,
            "nodes": [],
            "edges": [],
            "message": "Graph integration is scaffolded but not connected yet.",
        }
