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

# Download activities + health data from Garmin Connect (requires .env with GARMIN_PERSONAL_API_KEY)
python garmin_connect_downloader.py

# Run MCP server locally (STDIO, used by Claude Desktop)
.venv/bin/python mcp_server.py --transport stdio

# Run MCP server over HTTP (for remote clients, requires GARMIN_MCP_AUTH_TOKEN)
GARMIN_MCP_AUTH_TOKEN=<token> python mcp_server.py --transport http
```

No test framework is configured. There are no lint or format commands.

## Architecture

Two main components, both pure Python with no framework beyond the MCP SDK:

### `garmin_api.py` — Every read goes through the Personal API
- Garmin's Personal API (Oct 2026): a key from
  https://connect.garmin.com/app/settings/personalApiToken, no password/MFA/session.
  `GARMIN_PERSONAL_API_KEY` (`GARMIN_ACCESS_TOKEN` still read as a fallback).
- The key is POSTed (`Authorization: ApiKey …`) to
  `/personalapitoken-service/personal-api/personal-api-key/token` and comes back
  as a **bare JWT in text/plain, not JSON**, valid 24 h, no refresh token.
  Cached in-process until 5 min before `exp`; a 401 forces one re-exchange.
- Host `personal.connectapi.garmin.com`, **same paths as connectapi** — but not all
  of them. 404 on the Personal API: training readiness/status, max metrics, race
  predictions, endurance/hill score, blood pressure, devices, `socialProfile`,
  `/daily/respiration`, `/daily/spo2`, `floorsChartData`, `stats/im`, badge challenges.
- Range caps: stress/steps/sleep summaries 400 past ~28–31 days; v2 daily
  summaries fine at 6 months, 500 at a year. The activity list 500s for `limit` ≥ 500.
- It is **read-only**. Writes (upload, privacy, challenge opt-in) stay on garth.
- The key expires (30 d–1 y) and nothing Garmin returns says when;
  `GARMIN_PERSONAL_API_KEY_EXPIRES=YYYY-MM-DD` makes `/upload/health` report days left.

### `garmin_connect_downloader.py` — Data Ingestion
- `GarminConnectDownloader` reads only through `garmin_api` — no garth here
- `download_activities()` pages the activity list 200 at a time, passing the start date to Garmin
- `download_health_data()`: v2 daily summaries (90-day chunks) feed steps, stress,
  intensity minutes, floors, respiration, hydration and daily_body_battery; HRV,
  sleep and body composition are range queries; heart rate, SpO2
  (`spo2acclimation`) and fitness age (`v2`) are day-by-day, for the intraday
  series kept in `raw_json`
- Tables the Personal API cannot fill (training_readiness, training_status,
  daily_max_metrics, race_predictions, endurance_score, hill_score,
  blood_pressure, devices) keep their history and are no longer written
- Wellness data stops at 2026-08-16: the user moved to a COROS watch and only
  FIT files reach Garmin (via fit-bridge), so empty recent days are expected
- A summary section that is empty writes nothing, rather than nulls over existing rows
- Uses `INSERT OR REPLACE` upsert everywhere — calendar_date is the PK for health tables
- Config via `.env`: `GARMIN_PERSONAL_API_KEY`, `DB_PATH`, `GARMIN_LIMIT`, `GARMIN_START_DATE`

### `mcp_server.py` — MCP Server
- Uses Anthropic's `mcp` SDK with dual transport: STDIO (default, for local Claude Desktop) and Streamable HTTP (for remote clients, with bearer token auth)
- Read-only access to the SQLite database; `execute_sql` tool enforces SELECT-only queries
- 6 resources: activities, stats/summary, stats/monthly, activities/recent, health/summary, health/recent
- 9 tools: `query_activities`, `get_activity_details`, `get_power_analysis`, `get_training_trends`, `execute_sql`, `get_daily_health_summary`, `get_sleep_analysis`, `get_body_composition`, `get_health_trends`
- HTTP mode uses `StreamableHTTPSessionManager` (stateless) with `BearerAuthBackend` + `RequireAuthMiddleware`
- `--transport stdio` for local Claude Desktop, `--transport http` for remote clients
- HTTP mode serves both `/mcp` and `/mcp/` (the bare path is rewritten, not redirected)
- `deploy/garmin-mcp.service` — systemd unit for production deployment on Linux VPS

### `garmin_files.py` — Moving activity files in and out
- Reads (`fetch_activity_file`, `find_activity_by_start`) use the Personal API key;
  writes (`upload_fit`, `set_privacy`) and `garmin_challenges` use the garth session
  (`GARMIN_EMAIL`, `GARMIN_PASSWORD`, `GARTH_SESSION_PATH`)
- Owns the garth session (`authenticate()`), so a server importing it never
  inherits a CLI's `sys.exit`: a missing credential fails one request rather
  than taking the process down. `export_fit.py` delegates here and adds the
  exit itself.
- `fetch_activity_file()` — `/download-service/files/activity/{id}` serves a ZIP
  wrapping the .fit, but **some activities come back as a bare FIT**; both are
  unwrapped. `export_fit.py` uses this too, so the CLI and the REST API cannot
  drift apart about what Garmin actually serves.
- `upload_fit()` — `/upload-service/upload/fit`, plus the classification of
  Garmin's answer. **409 means duplicate**, and garth calls `raise_for_status()`
  so it arrives as an exception — unwrap `err.error.response.status_code`.
  Garmin usually answers **202 with no import result**, so a success commonly
  reports `uploaded` with no `activity_id`; resolving it needs a follow-up poll.
- garth's default timeout is **10 seconds for every request** and it passes that
  to requests itself, so a `timeout=` kwarg on `garth.client.post()` collides
  with it and raises `TypeError`. Use `garth.client.configure(timeout=...)`.
- `garth.upload()`-style calls need a real file handle — a bare `BytesIO` fails
  because garth reads `fp.name`.
- `GarminError.status` is what the REST layer reports: 503 by default, but
  Garmin's own status when Garmin answered, so an unknown activity is a 404 to
  the caller rather than a claim that Garmin is down.

### `garmin_challenges.py` — Badge challenges
- **The join verb is `optIn`, not `join`.** `POST
  /badgechallenge-service/badgeChallenge/{uuid}/optIn/{YYYY-MM-DD}` -> 204.
  Captured from the Connect web app 2026-08-28 after every `/join/…`,
  `/…/join`, `/player/…` shape 404'd, `OPTIONS` on the detail path reported
  only `HEAD,GET,OPTIONS`, and python-garminconnect turned out to expose
  challenges read-only. Do not go looking for it again.
- The 204 has **no body**, so it proves nothing changed hands — `opt_in()`
  reads the challenge back and returns Garmin's own view.
- **An already-joined challenge answers 400**, not 204. Reported as success
  when the read-back shows `userJoined`, so a retry after a timeout is safe.
- A bad uuid answers 400, a well-formed unknown one 404; both map to 404.
- Monthly/quarterly challenges arrive **already joined** (42 of 42), so
  `joinable` lists only expeditions. Joining moves one from
  `virtualChallenge/available` to `virtualChallenge/inProgress`.
- These read Garmin live, not the mirror: progress and join state change with
  no activity recorded, so there is nothing in the database to mirror.
- **Expeditions are one per `challengeGroupPk`** — group 1 distance trails,
  group 2 ascent climbs. Joining one turns every other expedition in that group
  `joinable: false` until it finishes, so `available` is not the same as
  joinable. Found 2026-08-28 by joining Rheinsteig Trail and watching the other
  ten group-1 trails close while all nine group-2 climbs stayed open.
- `join_challenges.py` is the cron entry point. It joins at most one per group
  by construction, so it takes `GARMIN_CHALLENGE_PREFER` — otherwise nine open
  climbs are decided alphabetically, which picks Elbrus by accident.

### REST API (`/api/v1`, HTTP mode only)
Carries only what MCP cannot — binary files and the one write path:
`/health` (unauthenticated), `/activities/{id}/file`, `/upload/health`,
`/upload/fit`. `/upload/health` is separate from `/health` because it costs a
session probe and needs credentials, whereas `/health` must stay cheap enough
to poll; callers use it as a batch preflight. It reports both ways in: the
garth session decides the status, the Personal API key and its expiry ride
alongside. `/health` only says whether a key is configured.

### Database
- SQLite with `activities` table (~90 columns) + 21 health/wellness tables
- Health tables: `daily_sleep`, `daily_stress`, `daily_hrv`, `daily_steps`, `daily_hydration`, `daily_intensity_minutes`, `body_composition`, `daily_body_battery`, `daily_heart_rate`, `daily_respiration`, `daily_spo2`, `daily_floors`, `training_readiness`, `training_status`, `blood_pressure`, `daily_max_metrics`, `fitness_age`, `race_predictions`, `endurance_score`, `hill_score`, `devices`
- Key units: distance in meters, duration in seconds, speed in m/s, weight in grams — the MCP server converts in query results
- `daily_health_summary` view joins steps/stress/HRV/sleep/body battery/heart rate/intensity/hydration
  over a UNION of every source table's dates, so a day missing one dataset still appears
- `activity_summary` view provides pre-calculated conversions (km, miles, pace, mph)
- `schema/schema_garmin.sql` is the canonical schema — `init_database()` executes this
  file directly, so the DDL exists in exactly one place
- Tables with `raw_json` column (heart rate, respiration, SpO2, floors, training, etc.) store the full API response for detailed analysis via `execute_sql` with SQLite JSON functions
