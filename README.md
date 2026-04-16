# Governance Risk Scanner

Company governance and financial risk scanning platform for A-share and Taiwan listed companies.

## Current scope

This repository currently contains:

- `project-blueprint-v2.md`: product and architecture blueprint
- `backend/`: Flask API, schema definitions, and rules engine skeleton
- `data/`: local JSON cache for company snapshots and signal outputs
- `frontend/`: frontend scaffold

## Backend quick start

```bash
cd /Users/wangyouqi/Documents/DesktopOrganizer/Web Development/C_G
python3 -m venv .venv
source .venv/bin/activate
pip install -r backend/requirements.txt
python3 -m backend.app
```

The API will start on `http://127.0.0.1:5000`.

## Sample endpoints

- `GET /api/health`
- `GET /api/search?q=茅台`
- `GET /api/company/CN/600519`
- `GET /api/signals/CN/600519`

## Master data build

```bash
python3 -m backend.master.build_master --require-live
```

This creates `backend/master/company_master.db`.

## Snapshot sync

```bash
python3 -m backend.scrapers.save_snapshots --require-live
```

This reads `backend/master/company_master.db` and writes normalized snapshots into `data/cn/` and `data/tw/`.

## Source probe

```bash
python3 -m backend.scrapers.probe_sources
```

Use this before a full run. If a source is not `live_available`, the `--require-live` commands will fail instead of silently falling back to demo data.

## Notes

- The API currently reads local JSON snapshots from `data/`.
- Scrapers, Neo4j importers, and AI reporting are scaffolded but not fully implemented yet.
