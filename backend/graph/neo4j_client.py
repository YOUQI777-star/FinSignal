from __future__ import annotations

from typing import Any

from backend.config import NEO4J_DATABASE, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD

# Optional import — neo4j driver may not be installed in all envs
try:
    from neo4j import GraphDatabase, exceptions as neo4j_exc
    _NEO4J_AVAILABLE = True
except ImportError:
    _NEO4J_AVAILABLE = False


def _bolt_uri(uri: str) -> str:
    """
    Convert neo4j+s:// to bolt+s:// for direct connection.

    AuraDB's routing protocol (neo4j+s://) returns internal cluster
    hostnames in its routing table that are not resolvable from hosted
    environments like Railway.  bolt+s:// connects directly to the
    public AuraDB endpoint without routing table lookup.
    """
    return uri.replace("neo4j+s://", "bolt+s://", 1)


class Neo4jClient:
    """
    Neo4j AuraDB client.

    Falls back gracefully when:
    - neo4j driver not installed
    - NEO4J_URI env var not set
    - AuraDB instance unreachable
    """

    def __init__(self) -> None:
        self._driver = None
        if _NEO4J_AVAILABLE and NEO4J_URI:
            try:
                self._driver = GraphDatabase.driver(
                    _bolt_uri(NEO4J_URI),
                    auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                )
                self._driver.verify_connectivity()
            except Exception:
                self._driver = None

    # ------------------------------------------------------------------
    # Public API — all return Cytoscape-compatible dicts
    # ------------------------------------------------------------------

    def get_company_graph(self, market: str, code: str) -> dict[str, Any]:
        """
        Return supply-chain subgraph for one company:
          - the Company node itself
          - its Industry nodes  (BELONGS_TO_INDUSTRY)
          - its Product nodes   (HAS_PRODUCT)
          - upstream Product nodes  (UPSTREAM_OF)
          - downstream Product nodes (DOWNSTREAM_OF)
        """
        if not self._driver:
            return self._empty(market, code)

        company_id = f"{market}:{code}"
        cypher = """
        MATCH (c:Company {company_id: $cid})
        OPTIONAL MATCH (c)-[:BELONGS_TO_INDUSTRY]->(ind:Industry)
        OPTIONAL MATCH (c)-[:HAS_PRODUCT]->(p:Product)
        OPTIONAL MATCH (p)-[:UPSTREAM_OF]->(up:Product)
        OPTIONAL MATCH (p)-[:DOWNSTREAM_OF]->(dn:Product)
        RETURN c, collect(DISTINCT ind) AS industries,
               collect(DISTINCT p)   AS products,
               collect(DISTINCT up)  AS upstreams,
               collect(DISTINCT dn)  AS downstreams
        """
        try:
            with self._driver.session(database=NEO4J_DATABASE) as session:
                rec = session.run(cypher, cid=company_id).single()
            if rec is None:
                return self._empty(market, code, found=False)
            return self._build_cytoscape(  # type: ignore[return-value]
                company_id,
                rec["c"],
                rec["industries"],
                rec["products"],
                rec["upstreams"],
                rec["downstreams"],
            )
        except Exception as exc:
            return self._empty(market, code, error=str(exc))

    def get_supply_chain(self, market: str, code: str) -> dict[str, Any]:
        """
        Return direct upstream suppliers and downstream customers
        (Company nodes connected via shared Products).
        """
        if not self._driver:
            return {"upstream": [], "downstream": []}

        company_id = f"{market}:{code}"
        cypher = """
        MATCH (c:Company {company_id: $cid})-[:HAS_PRODUCT]->(p:Product)
        OPTIONAL MATCH (p)-[:UPSTREAM_OF]->(up:Product)<-[:HAS_PRODUCT]-(supplier:Company)
        OPTIONAL MATCH (p)-[:DOWNSTREAM_OF]->(dn:Product)<-[:HAS_PRODUCT]-(customer:Company)
        RETURN
          collect(DISTINCT {company_id: supplier.company_id, name: supplier.name, code: supplier.code}) AS upstream,
          collect(DISTINCT {company_id: customer.company_id,  name: customer.name,  code: customer.code}) AS downstream
        """
        try:
            with self._driver.session(database=NEO4J_DATABASE) as session:
                rec = session.run(cypher, cid=company_id).single()
            if rec is None:
                return {"upstream": [], "downstream": []}
            return {
                "upstream":   [r for r in rec["upstream"]   if r.get("company_id")],
                "downstream": [r for r in rec["downstream"] if r.get("company_id")],
            }
        except Exception:
            return {"upstream": [], "downstream": []}

    def get_peer_companies(self, market: str, code: str, limit: int = 10) -> list[dict]:
        """Return companies sharing the same Industry node."""
        if not self._driver:
            return []

        company_id = f"{market}:{code}"
        cypher = """
        MATCH (c:Company {company_id: $cid})-[:BELONGS_TO_INDUSTRY]->(i:Industry)
              <-[:BELONGS_TO_INDUSTRY]-(peer:Company)
        WHERE peer.company_id <> $cid
        RETURN peer.company_id AS company_id, peer.name AS name,
               peer.code AS code, peer.market AS market,
               i.name AS industry
        LIMIT $limit
        """
        try:
            with self._driver.session(database=NEO4J_DATABASE) as session:
                rows = session.run(cypher, cid=company_id, limit=limit).data()
            return rows
        except Exception:
            return []

    def is_connected(self) -> bool:
        return self._driver is not None

    def close(self) -> None:
        if self._driver:
            self._driver.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _empty(market: str, code: str, found: bool = True, error: str = "") -> dict:
        msg = (
            error if error
            else ("No graph data found for this company." if not found
                  else "Neo4j not connected — check NEO4J_URI env var.")
        )
        return {
            "company_id": f"{market}:{code}",
            "nodes": [],
            "edges": [],
            "message": msg,
        }

    @staticmethod
    def _build_cytoscape(
        company_id: str,
        company_node: Any,
        industries: list,
        products: list,
        upstreams: list,
        downstreams: list,
    ) -> dict[str, Any]:
        nodes: list[dict] = []
        edges: list[dict] = []
        seen_nodes: set[str] = set()
        seen_edges: set[tuple] = set()

        def add_node(nid: str, label: str, data: dict) -> None:
            if nid not in seen_nodes:
                seen_nodes.add(nid)
                nodes.append({"data": {"id": nid, "label": label, "type": label, **data}})

        def add_edge(src: str, tgt: str, rel: str) -> None:
            key = (src, tgt, rel)
            if key not in seen_edges:
                seen_edges.add(key)
                edges.append({"data": {"source": src, "target": tgt, "relation": rel}})

        # Central company node
        cn = dict(company_node)
        add_node(company_id, "Company", {
            "name":   cn.get("name", company_id),
            "code":   cn.get("code", ""),
            "market": cn.get("market", ""),
        })

        # Industry nodes
        for ind in industries:
            if ind is None:
                continue
            d = dict(ind)
            nid = f"industry:{d.get('name','')}"
            add_node(nid, "Industry", {"name": d.get("name", "")})
            add_edge(company_id, nid, "BELONGS_TO_INDUSTRY")

        # Direct product nodes
        product_nids: dict[str, str] = {}
        for p in products:
            if p is None:
                continue
            d = dict(p)
            name = d.get("name", "")
            nid = f"product:{name}"
            product_nids[name] = nid
            add_node(nid, "Product", {"name": name})
            add_edge(company_id, nid, "HAS_PRODUCT")

        # Upstream product nodes
        for p in upstreams:
            if p is None:
                continue
            d = dict(p)
            name = d.get("name", "")
            nid = f"product:{name}"
            add_node(nid, "Product", {"name": name, "direction": "upstream"})
            # Connect to whichever direct product pointed upstream
            for pname, pnid in product_nids.items():
                add_edge(nid, pnid, "UPSTREAM_OF")
                break  # avoid fan-out; import script stores correct pairs

        # Downstream product nodes
        for p in downstreams:
            if p is None:
                continue
            d = dict(p)
            name = d.get("name", "")
            nid = f"product:{name}"
            add_node(nid, "Product", {"name": name, "direction": "downstream"})
            for pname, pnid in product_nids.items():
                add_edge(pnid, nid, "DOWNSTREAM_OF")
                break

        return {
            "company_id": company_id,
            "nodes": nodes,
            "edges": edges,
            "message": "",
        }
