"""
import_chain_kg.py
------------------
One-time (re-runnable) script that imports liuhuanyong/ChainKnowledgeGraph
into Neo4j AuraDB.

Data files expected at:  data/chain_kg/data/*.json  (JSONL format)

Mapping strategy
----------------
ChainKnowledgeGraph uses codes like "600373.SH" or bare "301079".
We strip the exchange suffix (.SH / .SZ / .BJ) and look up the
6-digit code in company_master.db.  Only matched companies are imported;
unmatched codes are written to data/chain_kg/unmatched.log.

Run
---
    python -m backend.graph.import_chain_kg
    python -m backend.graph.import_chain_kg --dry-run   # validate without writing
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path
from typing import Iterator

from backend.config import DATA_DIR, NEO4J_DATABASE, NEO4J_PASSWORD, NEO4J_URI, NEO4J_USERNAME

try:
    from neo4j import GraphDatabase
    _DRIVER_AVAILABLE = True
except ImportError:
    _DRIVER_AVAILABLE = False

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger(__name__)

CHAIN_KG_DIR = DATA_DIR / "chain_kg" / "data"
MASTER_DB    = DATA_DIR.parent / "backend" / "master" / "company_master.db"
UNMATCHED_LOG = DATA_DIR / "chain_kg" / "unmatched.log"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _strip_suffix(code: str) -> str:
    """'600373.SH' → '600373',  '301079' → '301079'"""
    return code.split(".")[0].strip()


def _read_jsonl(path: Path) -> Iterator[dict]:
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue


def _load_master_codes(db_path: Path) -> dict[str, dict]:
    """Return {code: {company_id, name, market}} for all CN companies."""
    conn = sqlite3.connect(db_path)
    rows = conn.execute(
        "SELECT company_id, code, market, name FROM company_master WHERE market='CN'"
    ).fetchall()
    conn.close()
    return {r[1]: {"company_id": r[0], "code": r[1], "market": r[2], "name": r[3]}
            for r in rows}


# ---------------------------------------------------------------------------
# Import phases
# ---------------------------------------------------------------------------

def _import_industries(session, dry_run: bool) -> dict[str, str]:
    """Create Industry nodes. Returns {industry_name: node_id}."""
    log.info("Importing Industry nodes …")
    rows = list(_read_jsonl(CHAIN_KG_DIR / "industry.json"))
    if not dry_run:
        session.run("CREATE CONSTRAINT industry_name IF NOT EXISTS "
                    "FOR (i:Industry) REQUIRE i.name IS UNIQUE")
        for row in rows:
            name = row.get("name", "").strip()
            if not name:
                continue
            session.run(
                "MERGE (i:Industry {name: $name}) "
                "SET i.code = $code",
                name=name, code=row.get("code", ""),
            )
    log.info("  %d industry rows processed", len(rows))
    return {r["name"]: r.get("code", "") for r in rows if r.get("name")}


def _import_products(session, dry_run: bool) -> None:
    """Create Product nodes (bulk)."""
    log.info("Importing Product nodes …")
    rows = list(_read_jsonl(CHAIN_KG_DIR / "product.json"))
    if not dry_run:
        session.run("CREATE CONSTRAINT product_name IF NOT EXISTS "
                    "FOR (p:Product) REQUIRE p.name IS UNIQUE")
        batch: list[str] = []
        for row in rows:
            name = row.get("name", "").strip()
            if name:
                batch.append(name)
            if len(batch) >= 500:
                session.run(
                    "UNWIND $names AS n MERGE (p:Product {name: n})",
                    names=batch,
                )
                batch.clear()
        if batch:
            session.run("UNWIND $names AS n MERGE (p:Product {name: n})", names=batch)
    log.info("  %d product rows processed", len(rows))


def _import_companies(
    session,
    master: dict[str, dict],
    dry_run: bool,
) -> tuple[dict[str, str], list[str]]:
    """
    Create Company nodes for codes that exist in company_master.
    Returns ({raw_code: company_id}, [unmatched_codes]).
    """
    log.info("Importing Company nodes …")
    rows = list(_read_jsonl(CHAIN_KG_DIR / "company.json"))
    mapped: dict[str, str] = {}
    unmatched: list[str] = []

    if not dry_run:
        session.run("CREATE CONSTRAINT company_id IF NOT EXISTS "
                    "FOR (c:Company) REQUIRE c.company_id IS UNIQUE")

    for row in rows:
        raw_code = row.get("code", "").strip()
        code = _strip_suffix(raw_code)
        m = master.get(code)
        if m is None:
            unmatched.append(raw_code)
            continue
        mapped[raw_code] = m["company_id"]
        if not dry_run:
            session.run(
                """
                MERGE (c:Company {company_id: $cid})
                SET c.code   = $code,
                    c.market = $market,
                    c.name   = $name
                """,
                cid=m["company_id"], code=code,
                market=m["market"], name=m["name"],
            )

    log.info("  matched=%d  unmatched=%d", len(mapped), len(unmatched))
    return mapped, unmatched


def _import_company_industry(
    session, mapped: dict[str, str], dry_run: bool
) -> None:
    log.info("Importing BELONGS_TO_INDUSTRY relationships …")
    rows = list(_read_jsonl(CHAIN_KG_DIR / "company_industry.json"))
    count = 0
    for row in rows:
        raw_code = row.get("company_code", "").strip()
        code = _strip_suffix(raw_code)
        # company_industry.json uses raw codes with suffix
        cid = mapped.get(raw_code) or mapped.get(code)
        if cid is None:
            continue
        industry = row.get("industry_name", "").strip()
        if not industry:
            continue
        if not dry_run:
            session.run(
                """
                MATCH (c:Company {company_id: $cid})
                MERGE (i:Industry {name: $industry})
                MERGE (c)-[:BELONGS_TO_INDUSTRY]->(i)
                """,
                cid=cid, industry=industry,
            )
        count += 1
    log.info("  %d relationships created", count)


def _import_company_product(
    session, mapped: dict[str, str], dry_run: bool
) -> None:
    log.info("Importing HAS_PRODUCT relationships …")
    rows = list(_read_jsonl(CHAIN_KG_DIR / "company_product.json"))
    count = 0
    batch: list[dict] = []

    for row in rows:
        raw_code = row.get("company_code", "").strip()
        code = _strip_suffix(raw_code)
        cid = mapped.get(raw_code) or mapped.get(code)
        if cid is None:
            continue
        product = row.get("product_name", "").strip()
        if not product:
            continue
        batch.append({"cid": cid, "product": product,
                      "weight": row.get("rel_weight", 0.0)})
        count += 1
        if len(batch) >= 200 and not dry_run:
            session.run(
                """
                UNWIND $rows AS r
                MATCH (c:Company {company_id: r.cid})
                MERGE (p:Product {name: r.product})
                MERGE (c)-[rel:HAS_PRODUCT]->(p)
                SET rel.weight = r.weight
                """,
                rows=batch,
            )
            batch.clear()

    if batch and not dry_run:
        session.run(
            """
            UNWIND $rows AS r
            MATCH (c:Company {company_id: r.cid})
            MERGE (p:Product {name: r.product})
            MERGE (c)-[rel:HAS_PRODUCT]->(p)
            SET rel.weight = r.weight
            """,
            rows=batch,
        )
    log.info("  %d relationships created", count)


def _import_product_product(session, dry_run: bool) -> None:
    log.info("Importing UPSTREAM_OF / DOWNSTREAM_OF relationships …")
    rows = list(_read_jsonl(CHAIN_KG_DIR / "product_product.json"))
    count = 0
    batch: list[dict] = []

    for row in rows:
        frm = row.get("from_entity", "").strip()
        to  = row.get("to_entity",   "").strip()
        rel = row.get("rel", "").strip()
        if not frm or not to or not rel:
            continue
        # 上游材料 → UPSTREAM_OF;  下游产品 → DOWNSTREAM_OF
        if "上游" in rel:
            rel_type = "UPSTREAM_OF"
        elif "下游" in rel:
            rel_type = "DOWNSTREAM_OF"
        else:
            continue
        batch.append({"frm": frm, "to": to, "rel": rel_type})
        count += 1
        if len(batch) >= 500 and not dry_run:
            session.run(
                """
                UNWIND $rows AS r
                MERGE (a:Product {name: r.frm})
                MERGE (b:Product {name: r.to})
                FOREACH(_ IN CASE r.rel WHEN 'UPSTREAM_OF'   THEN [1] ELSE [] END |
                    MERGE (a)-[:UPSTREAM_OF]->(b))
                FOREACH(_ IN CASE r.rel WHEN 'DOWNSTREAM_OF' THEN [1] ELSE [] END |
                    MERGE (a)-[:DOWNSTREAM_OF]->(b))
                """,
                rows=batch,
            )
            batch.clear()

    if batch and not dry_run:
        session.run(
            """
            UNWIND $rows AS r
            MERGE (a:Product {name: r.frm})
            MERGE (b:Product {name: r.to})
            FOREACH(_ IN CASE r.rel WHEN 'UPSTREAM_OF'   THEN [1] ELSE [] END |
                MERGE (a)-[:UPSTREAM_OF]->(b))
            FOREACH(_ IN CASE r.rel WHEN 'DOWNSTREAM_OF' THEN [1] ELSE [] END |
                MERGE (a)-[:DOWNSTREAM_OF]->(b))
            """,
            rows=batch,
        )
    log.info("  %d relationships created", count)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def run(dry_run: bool = False) -> None:
    if not _DRIVER_AVAILABLE:
        raise RuntimeError("neo4j driver not installed. Run: pip install neo4j")
    if not NEO4J_URI:
        raise RuntimeError("NEO4J_URI env var not set.")

    log.info("Connecting to Neo4j … (dry_run=%s)", dry_run)
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    driver.verify_connectivity()
    log.info("Connected.")

    master = _load_master_codes(MASTER_DB)
    log.info("Loaded %d CN companies from company_master", len(master))

    # AuraDB Free names the user database after the instance ID (e.g. "65af9e9c")
    with driver.session(database=NEO4J_DATABASE) as session:
        _import_industries(session, dry_run)
        _import_products(session, dry_run)
        mapped, unmatched = _import_companies(session, master, dry_run)
        _import_company_industry(session, mapped, dry_run)
        _import_company_product(session, mapped, dry_run)
        _import_product_product(session, dry_run)

    # Write unmatched log
    if not dry_run and unmatched:
        UNMATCHED_LOG.parent.mkdir(parents=True, exist_ok=True)
        UNMATCHED_LOG.write_text("\n".join(unmatched), encoding="utf-8")
        log.info("Unmatched codes written to %s (%d entries)", UNMATCHED_LOG, len(unmatched))

    driver.close()
    log.info("Import complete.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Import ChainKnowledgeGraph into Neo4j")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate data without writing to Neo4j")
    args = parser.parse_args()
    run(dry_run=args.dry_run)


if __name__ == "__main__":
    main()
