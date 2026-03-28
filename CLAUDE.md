# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Garmin Connect MCP Server — a Python app that downloads Garmin Connect fitness activities into a SQLite database and exposes them via a Model Context Protocol (MCP) server for AI-powered querying.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Download activities from Garmin Connect (requires .env with GARMIN_EMAIL/GARMIN_PASSWORD)
python garmin_connect_downloader.py

# Run MCP server (used by Claude Desktop / MCP clients)
./run_mcp_server.sh
```

No test framework is configured. There are no lint or format commands.

## Architecture

Two main components, both pure Python with no framework beyond the MCP SDK:

### `garmin_connect_downloader.py` — Data Ingestion
- `GarminConnectDownloader` class handles auth (via `garth` library with MFA/session persistence), API calls, and DB writes
- Auth flow: tries resuming saved session from `GARTH_SESSION_PATH`, falls back to fresh login
- Downloads from Garmin's `/activitylist-service/activities/search/activities` endpoint
- Uses `INSERT OR REPLACE` for upsert behavior — activity_id is the primary key
- Nested Garmin API objects (activityType, eventType, privacy) are flattened into columns
- Config via `.env`: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `DB_PATH`, `GARMIN_LIMIT`, `GARMIN_START_DATE`, `GARTH_SESSION_PATH`

### `mcp_server.py` — MCP Server
- Uses Anthropic's `mcp` SDK with STDIO transport (`mcp.server.stdio`)
- Read-only access to the SQLite database; `execute_sql` tool enforces SELECT-only queries
- Exposes 4 resources (`garmin://activities`, `garmin://stats/summary`, `garmin://stats/monthly`, `garmin://activities/recent`) and 5 tools (`query_activities`, `get_activity_details`, `get_power_analysis`, `get_training_trends`, `execute_sql`)
- `run_mcp_server.sh` is the launcher: activates `.venv` and runs `mcp_server.py`
- DB path resolved from `GARMIN_DB_PATH` env var, defaulting to `garmin_activities.db` in the project root

### Database
- SQLite with ~90 columns in the `activities` table matching Garmin's API response shape
- Key units: distance in meters, duration in seconds, speed in m/s — the MCP server converts to km/minutes/km·h⁻¹ in query results
- `activity_summary` view provides pre-calculated conversions (km, miles, pace, mph)
- `schema_garmin.sql` is the canonical schema reference (includes lookup tables and seed data not in the downloader's inline DDL)
- `garmin_activity_schema.json` is a sample Garmin API response for field reference
