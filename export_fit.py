#!/usr/bin/env python3
"""
Export original activity files (FIT) from Garmin Connect.

Garmin serves the originally recorded file from
/download-service/files/activity/{id} as a ZIP wrapping the .fit. This script
downloads them into exports/, keeping a JSON ledger so an interrupted run
resumes instead of starting over.

Usage:
    python export_fit.py --ids 123,456          # specific activities
    python export_fit.py --all                  # every activity in the DB
    python export_fit.py --all --limit 50       # first 50 (newest first)
"""

import argparse
import json
import os
import sqlite3
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

import garmin_files

BASE = Path(__file__).parent
EXPORT_DIR = BASE / "exports"
LEDGER_PATH = EXPORT_DIR / "_ledger.json"
DB_PATH = os.getenv("DB_PATH", str(BASE / "garmin_activities.db"))

# Garmin throttles aggressive downloading; this pace has headroom.
SLEEP_BETWEEN = 1.5


def authenticate() -> None:
    """
    Resume a saved garth session, or log in fresh.

    The session itself belongs to garmin_files, so that the MCP server can use
    it without inheriting the exit below. This wrapper adds what a CLI wants:
    a line saying what happened, and a hard stop when there is no way in.
    """
    try:
        garmin_files.authenticate()
    except garmin_files.GarminError as e:
        print(f"❌ {e}")
        sys.exit(1)
    print("✅ Garmin session ready")


def load_ledger() -> dict:
    if LEDGER_PATH.exists():
        try:
            return json.loads(LEDGER_PATH.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_ledger(ledger: dict) -> None:
    LEDGER_PATH.write_text(json.dumps(ledger, indent=2))


def download_one(activity_id: int) -> tuple:
    """
    Download one activity into exports/. Returns (status, detail).

    The fetch and the ZIP unwrap live in garmin_files, so the REST API and this
    CLI cannot drift apart about what Garmin actually serves.
    """
    try:
        data, _ = garmin_files.fetch_activity_file(activity_id)
    except garmin_files.GarminError as e:
        return "error", str(e)

    out = EXPORT_DIR / f"{activity_id}.fit"
    out.write_bytes(data)
    return "ok", len(data)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export Garmin FIT files")
    parser.add_argument("--ids", help="Comma-separated activity IDs")
    parser.add_argument("--all", action="store_true", help="Export every activity in the DB")
    parser.add_argument("--limit", type=int, default=None, help="Cap the number exported")
    parser.add_argument("--retry-failed", action="store_true",
                        help="Retry IDs previously recorded as failed")
    args = parser.parse_args()

    EXPORT_DIR.mkdir(exist_ok=True)
    ledger = load_ledger()

    if args.ids:
        ids = [int(x) for x in args.ids.split(",") if x.strip()]
    elif args.all:
        with sqlite3.connect(DB_PATH) as conn:
            rows = conn.execute(
                "SELECT activity_id FROM activities ORDER BY start_time_local DESC"
            ).fetchall()
        ids = [r[0] for r in rows]
    else:
        parser.error("Pass --ids or --all")

    # Skip anything already exported, unless explicitly retrying failures.
    pending = []
    for i in ids:
        entry = ledger.get(str(i))
        if entry and entry.get("status") == "ok" and (EXPORT_DIR / f"{i}.fit").exists():
            continue
        if entry and entry.get("status") != "ok" and not args.retry_failed and not args.ids:
            continue
        pending.append(i)

    if args.limit:
        pending = pending[: args.limit]

    print(f"📥 {len(pending)} to export ({len(ids) - len(pending)} already done)")
    authenticate()

    ok = failed = 0
    for n, activity_id in enumerate(pending, 1):
        try:
            status, detail = download_one(activity_id)
            ledger[str(activity_id)] = {"status": status, "detail": detail}
            if status == "ok":
                ok += 1
                print(f"  [{n}/{len(pending)}] ✅ {activity_id} ({detail:,} bytes)")
            else:
                failed += 1
                print(f"  [{n}/{len(pending)}] ⚠️  {activity_id}: {status} — {detail}")
        except Exception as e:
            failed += 1
            msg = str(e)[:160]
            ledger[str(activity_id)] = {"status": "error", "detail": msg}
            print(f"  [{n}/{len(pending)}] ❌ {activity_id}: {msg}")
            if "429" in msg or "Too Many" in msg:
                print("     ⏳ rate limited, pausing 60s")
                time.sleep(60)

        if n % 25 == 0:
            save_ledger(ledger)
        time.sleep(SLEEP_BETWEEN)

    save_ledger(ledger)
    total_bytes = sum(f.stat().st_size for f in EXPORT_DIR.glob("*.fit"))
    print(f"\n✅ {ok} exported, {failed} failed")
    print(f"📦 {len(list(EXPORT_DIR.glob('*.fit')))} files, {total_bytes / 1e6:.1f} MB in {EXPORT_DIR}")


if __name__ == "__main__":
    main()
