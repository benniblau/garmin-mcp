# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Garmin Connect MCP Server — a Python app that downloads Garmin Connect fitness activities and health/wellness data into a SQLite database and exposes them via a Model Context Protocol (MCP) server for AI-powered querying.

## Commands

```bash
# Setup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# Download activities + health data from Garmin Connect (requires .env with GARMIN_EMAIL/GARMIN_PASSWORD)
python garmin_connect_downloader.py

# Run MCP server locally (STDIO, used by Claude Desktop)
./run_mcp_server.sh

# Run MCP server over HTTP (for remote clients, requires MCP_AUTH_TOKEN)
MCP_AUTH_TOKEN=<token> python mcp_server.py --transport http
```

No test framework is configured. There are no lint or format commands.

## Architecture

Two main components, both pure Python with no framework beyond the MCP SDK:

### `garmin_connect_downloader.py` — Data Ingestion
- `GarminConnectDownloader` class handles auth (via `garth` library with MFA/session persistence), API calls, and DB writes
- Auth flow: tries resuming saved session from `GARTH_SESSION_PATH`, falls back to fresh login
- `download_activities()` — activities from `/activitylist-service/activities/search/activities`
- `download_health_data()` — all health/wellness data (sleep, stress, HRV, steps, hydration, body composition, heart rate, body battery, respiration, SpO2, floors, training readiness/status, blood pressure, max metrics, fitness age, race predictions, endurance/hill scores, devices)
- Health data uses garth's Stats classes for bulk range queries (steps, stress, HRV, hydration, intensity minutes) and day-by-day iteration for detailed data (sleep, body battery) and raw API calls (heart rate, respiration, SpO2, etc.)
- Uses `INSERT OR REPLACE` upsert everywhere — calendar_date is the PK for health tables
- Config via `.env`: `GARMIN_EMAIL`, `GARMIN_PASSWORD`, `DB_PATH`, `GARMIN_LIMIT`, `GARMIN_START_DATE`, `GARTH_SESSION_PATH`

### `mcp_server.py` — MCP Server
- Uses Anthropic's `mcp` SDK with dual transport: STDIO (default, for local Claude Desktop) and Streamable HTTP (for remote clients, with bearer token auth)
- Read-only access to the SQLite database; `execute_sql` tool enforces SELECT-only queries
- 6 resources: activities, stats/summary, stats/monthly, activities/recent, health/summary, health/recent
- 9 tools: `query_activities`, `get_activity_details`, `get_power_analysis`, `get_training_trends`, `execute_sql`, `get_daily_health_summary`, `get_sleep_analysis`, `get_body_composition`, `get_health_trends`
- HTTP mode uses `StreamableHTTPSessionManager` (stateless) with `BearerAuthBackend` + `RequireAuthMiddleware`
- `run_mcp_server.sh` is the STDIO launcher; `--transport http` for HTTP mode
- `deploy/garmin-mcp.service` — systemd unit for production deployment on Linux VPS

### Database
- SQLite with `activities` table (~90 columns) + 21 health/wellness tables
- Health tables: `daily_sleep`, `daily_stress`, `daily_hrv`, `daily_steps`, `daily_hydration`, `daily_intensity_minutes`, `body_composition`, `daily_body_battery`, `daily_heart_rate`, `daily_respiration`, `daily_spo2`, `daily_floors`, `training_readiness`, `training_status`, `blood_pressure`, `daily_max_metrics`, `fitness_age`, `race_predictions`, `endurance_score`, `hill_score`, `devices`
- Key units: distance in meters, duration in seconds, speed in m/s, weight in grams — the MCP server converts in query results
- `daily_health_summary` view joins steps/stress/HRV/sleep/body battery/heart rate/intensity/hydration
- `activity_summary` view provides pre-calculated conversions (km, miles, pace, mph)
- `schema/schema_garmin.sql` is the canonical schema reference
- Tables with `raw_json` column (heart rate, respiration, SpO2, floors, training, etc.) store the full API response for detailed analysis via `execute_sql` with SQLite JSON functions
