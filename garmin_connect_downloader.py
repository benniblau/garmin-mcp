#!/usr/bin/env python3
"""
Garmin Connect Activities Downloader

Reads through Garmin's Personal API (see garmin_api.py) — a key, no password,
no MFA, no session file. Downloads activities and inserts them into a database
schema that matches the Garmin Connect API response structure.

Author: Generated with Claude Code
"""

import argparse
import json
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Any, List
from dotenv import load_dotenv

# Load environment variables before garmin_api reads its configuration
load_dotenv()

import garmin_api  # noqa: E402

ACTIVITY_SEARCH = '/activitylist-service/activities/search/activities'

# The activity list answers 500 for a limit of 500 or more.
PAGE_SIZE = 200

# Range endpoints answer 400 past roughly a month, so ranges go in chunks.
RANGE_CHUNK_DAYS = 28

# Canonical schema — the downloader creates the database from this file so the
# DDL lives in exactly one place.
SCHEMA_PATH = Path(__file__).parent / "schema" / "schema_garmin.sql"


class GarminConnectDownloader:
    """Garmin Connect downloader over the Personal API."""

    def __init__(self, db_path: str = os.getenv('DB_PATH')):
        self.db_path = db_path
        self.init_database()
        self.authenticate()
    
    def init_database(self):
        """Initialize the SQLite database from schema/schema_garmin.sql."""
        print(f"Initializing Garmin database: {self.db_path}")

        if not SCHEMA_PATH.exists():
            print(f"❌ Schema file not found: {SCHEMA_PATH}")
            raise FileNotFoundError(SCHEMA_PATH)

        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # schema_garmin.sql is the single source of truth for the schema.
            # Every statement is IF NOT EXISTS, so this is safe to re-run.
            cursor.executescript(SCHEMA_PATH.read_text())

            conn.commit()
            conn.close()
            print("✅ Garmin database initialized successfully")

        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            raise

    def authenticate(self):
        """Exchange the Personal API key for a token — proves the key works."""
        print("🔐 Exchanging Garmin Personal API key for a token...")
        try:
            garmin_api.token()
        except garmin_api.ApiError as e:
            print(f"❌ {e}")
            raise
        print("✅ Personal API token ready")

    def download_activities(self, limit=None, start: int = 0, days_back=None):
        """
        Download activities, newest first, into the activities table.

        The Personal API answers 500 for a `limit` of 500 or more, so this
        pages through PAGE_SIZE at a time until `limit` is reached or Garmin
        runs out. A start date (--days, else GARMIN_START_DATE) is passed to
        Garmin as `startDate` rather than filtered here.
        """
        limit = int(limit if limit is not None else os.getenv('GARMIN_LIMIT') or 100)

        start_date = None
        if days_back is not None:
            start_date = (date.today() - timedelta(days=days_back)).isoformat()
        elif os.getenv('GARMIN_START_DATE'):
            try:
                start_date = datetime.strptime(os.getenv('GARMIN_START_DATE'), '%Y-%m-%d').date().isoformat()
            except ValueError:
                print(f"⚠️  Invalid GARMIN_START_DATE {os.getenv('GARMIN_START_DATE')!r}, expected YYYY-MM-DD. Ignoring it.")

        print(f"📥 Downloading up to {limit} activities"
              + (f" since {start_date}" if start_date else "") + "...")

        inserted_count = updated_count = fetched = 0
        offset = start
        while fetched < limit:
            params = {'start': offset, 'limit': min(PAGE_SIZE, limit - fetched)}
            if start_date:
                params['startDate'] = start_date
                params['endDate'] = date.today().isoformat()
            page = garmin_api.get(ACTIVITY_SEARCH, params=params) or []
            if not page:
                break

            for activity in page:
                try:
                    if self.insert_activity(activity):
                        updated_count += 1
                    else:
                        inserted_count += 1
                except Exception as e:
                    print(f"⚠️  Error processing activity {activity.get('activityId', 'unknown')}: {e}")

            fetched += len(page)
            offset += len(page)
            print(f"📝 Processed {fetched} activities...")
            if len(page) < params['limit']:
                break

        if not fetched:
            print("📭 No activities found!")
            return 0

        print(f"✅ Successfully processed {fetched} activities")
        print(f"   📊 New activities: {inserted_count}")
        print(f"   🔄 Updated activities: {updated_count}")
        return fetched
    
    def insert_activity(self, activity: Dict[str, Any]) -> bool:
        """Insert a single Garmin activity into the database. Returns True if updated, False if new."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        try:
            # Check if activity already exists
            cursor.execute("SELECT activity_id FROM activities WHERE activity_id = ?", 
                          (activity.get('activityId'),))
            exists = cursor.fetchone() is not None
            
            # Extract nested objects with proper defaults
            activity_type = activity.get('activityType', {})
            event_type = activity.get('eventType', {})
            privacy = activity.get('privacy', {})
            
            # Debug: Check if we have the expected number of values
            test_values = [
                activity.get('activityId'),
                activity.get('activityName'),
                activity.get('startTimeLocal'),
                activity.get('startTimeGMT'),
                activity.get('endTimeGMT'),
                activity.get('beginTimestamp'),
                activity_type.get('typeId'),
                activity_type.get('typeKey'),
                activity_type.get('parentTypeId'),
                activity_type.get('isHidden'),
                activity_type.get('restricted'),
                activity_type.get('trimmable'),
                activity.get('sportTypeId'),
                event_type.get('typeId'),
                event_type.get('typeKey'),
                event_type.get('sortOrder'),
                activity.get('duration'),
                activity.get('elapsedDuration'),
                activity.get('movingDuration'),
                activity.get('minActivityLapDuration'),
                activity.get('distance'),
                activity.get('elevationGain'),
                activity.get('elevationLoss'),
                activity.get('minElevation'),
                activity.get('maxElevation'),
                activity.get('maxVerticalSpeed'),
                activity.get('averageSpeed'),
                activity.get('maxSpeed'),
                activity.get('startLatitude'),
                activity.get('startLongitude'),
                activity.get('endLatitude'),
                activity.get('endLongitude'),
                activity.get('timeZoneId'),
                activity.get('ownerId'),
                activity.get('ownerDisplayName'),
                activity.get('ownerFullName'),
                activity.get('ownerProfileImageUrlSmall'),
                activity.get('ownerProfileImageUrlMedium'),
                activity.get('ownerProfileImageUrlLarge'),
                activity.get('userPro', False),
                activity.get('averageHR'),
                activity.get('maxHR'),
                activity.get('hrTimeInZone_1'),
                activity.get('hrTimeInZone_2'),
                activity.get('hrTimeInZone_3'),
                activity.get('hrTimeInZone_4'),
                activity.get('hrTimeInZone_5'),
                activity.get('avgPower'),
                activity.get('maxPower'),
                activity.get('normPower'),
                activity.get('max20MinPower'),
                activity.get('maxAvgPower_1'),
                activity.get('maxAvgPower_2'),
                activity.get('maxAvgPower_5'),
                activity.get('maxAvgPower_10'),
                activity.get('maxAvgPower_20'),
                activity.get('maxAvgPower_30'),
                activity.get('maxAvgPower_60'),
                activity.get('maxAvgPower_120'),
                activity.get('maxAvgPower_300'),
                activity.get('maxAvgPower_600'),
                activity.get('maxAvgPower_1200'),
                activity.get('maxAvgPower_1800'),
                activity.get('excludeFromPowerCurveReports', False),
                activity.get('powerTimeInZone_1'),
                activity.get('powerTimeInZone_2'),
                activity.get('powerTimeInZone_3'),
                activity.get('powerTimeInZone_4'),
                activity.get('powerTimeInZone_5'),
                activity.get('powerTimeInZone_6'),
                activity.get('powerTimeInZone_7'),
                activity.get('averageBikingCadenceInRevPerMinute'),
                activity.get('maxBikingCadenceInRevPerMinute'),
                activity.get('aerobicTrainingEffect'),
                activity.get('anaerobicTrainingEffect'),
                activity.get('trainingEffectLabel'),
                activity.get('aerobicTrainingEffectMessage'),
                activity.get('anaerobicTrainingEffectMessage'),
                activity.get('activityTrainingLoad'),
                activity.get('moderateIntensityMinutes'),
                activity.get('vigorousIntensityMinutes'),
                activity.get('calories'),
                activity.get('deviceId'),
                activity.get('manufacturer'),
                activity.get('hasPolyline', False),
                activity.get('hasImages', False),
                activity.get('hasVideo', False),
                activity.get('hasHeatMap', False),
                activity.get('hasSplits', False),
                activity.get('manualActivity', False),
                activity.get('autoCalcCalories', False),
                activity.get('elevationCorrected', False),
                activity.get('atpActivity', False),
                activity.get('favorite', False),
                activity.get('pr', False),
                activity.get('purposeful', False),
                activity.get('qualifyingDive', False),
                activity.get('decoDive', False),
                activity.get('parent', False),
                activity.get('lapCount'),
                privacy.get('typeId'),
                privacy.get('typeKey'),
                activity.get('strokes'),
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat()
            ]
            
            non_none_count = len([v for v in test_values if v is not None])
            print(f"🔍 Debug: Activity {activity.get('activityId')} - Total values: {len(test_values)}, Non-None: {non_none_count}")
            
            # Create a data dictionary with proper defaults
            now = datetime.now(timezone.utc).isoformat()
            
            activity_data = {
                'activity_id': activity.get('activityId'),
                'activity_name': activity.get('activityName'),
                'start_time_local': activity.get('startTimeLocal'),
                'start_time_gmt': activity.get('startTimeGMT'),
                'end_time_gmt': activity.get('endTimeGMT'),
                'begin_timestamp': activity.get('beginTimestamp'),
                'activity_type_id': activity_type.get('typeId'),
                'activity_type_key': activity_type.get('typeKey'),
                'activity_type_parent_id': activity_type.get('parentTypeId'),
                'activity_type_is_hidden': activity_type.get('isHidden', False),
                'activity_type_restricted': activity_type.get('restricted', False),
                'activity_type_trimmable': activity_type.get('trimmable', False),
                'sport_type_id': activity.get('sportTypeId'),
                'event_type_id': event_type.get('typeId'),
                'event_type_key': event_type.get('typeKey'),
                'event_type_sort_order': event_type.get('sortOrder'),
                'duration': activity.get('duration'),
                'elapsed_duration': activity.get('elapsedDuration'),
                'moving_duration': activity.get('movingDuration'),
                'min_activity_lap_duration': activity.get('minActivityLapDuration'),
                'distance': activity.get('distance'),
                'elevation_gain': activity.get('elevationGain'),
                'elevation_loss': activity.get('elevationLoss'),
                'min_elevation': activity.get('minElevation'),
                'max_elevation': activity.get('maxElevation'),
                'max_vertical_speed': activity.get('maxVerticalSpeed'),
                'average_speed': activity.get('averageSpeed'),
                'max_speed': activity.get('maxSpeed'),
                'start_latitude': activity.get('startLatitude'),
                'start_longitude': activity.get('startLongitude'),
                'end_latitude': activity.get('endLatitude'),
                'end_longitude': activity.get('endLongitude'),
                'time_zone_id': activity.get('timeZoneId'),
                'owner_id': activity.get('ownerId'),
                'owner_display_name': activity.get('ownerDisplayName'),
                'owner_full_name': activity.get('ownerFullName'),
                'owner_profile_image_small': activity.get('ownerProfileImageUrlSmall'),
                'owner_profile_image_medium': activity.get('ownerProfileImageUrlMedium'),
                'owner_profile_image_large': activity.get('ownerProfileImageUrlLarge'),
                'user_pro': activity.get('userPro', False),
                'average_hr': activity.get('averageHR'),
                'max_hr': activity.get('maxHR'),
                'hr_time_in_zone_1': activity.get('hrTimeInZone_1'),
                'hr_time_in_zone_2': activity.get('hrTimeInZone_2'),
                'hr_time_in_zone_3': activity.get('hrTimeInZone_3'),
                'hr_time_in_zone_4': activity.get('hrTimeInZone_4'),
                'hr_time_in_zone_5': activity.get('hrTimeInZone_5'),
                'avg_power': activity.get('avgPower'),
                'max_power': activity.get('maxPower'),
                'norm_power': activity.get('normPower'),
                'max_20min_power': activity.get('max20MinPower'),
                'max_avg_power_1': activity.get('maxAvgPower_1'),
                'max_avg_power_2': activity.get('maxAvgPower_2'),
                'max_avg_power_5': activity.get('maxAvgPower_5'),
                'max_avg_power_10': activity.get('maxAvgPower_10'),
                'max_avg_power_20': activity.get('maxAvgPower_20'),
                'max_avg_power_30': activity.get('maxAvgPower_30'),
                'max_avg_power_60': activity.get('maxAvgPower_60'),
                'max_avg_power_120': activity.get('maxAvgPower_120'),
                'max_avg_power_300': activity.get('maxAvgPower_300'),
                'max_avg_power_600': activity.get('maxAvgPower_600'),
                'max_avg_power_1200': activity.get('maxAvgPower_1200'),
                'max_avg_power_1800': activity.get('maxAvgPower_1800'),
                'exclude_from_power_curve_reports': activity.get('excludeFromPowerCurveReports', False),
                'power_time_in_zone_1': activity.get('powerTimeInZone_1'),
                'power_time_in_zone_2': activity.get('powerTimeInZone_2'),
                'power_time_in_zone_3': activity.get('powerTimeInZone_3'),
                'power_time_in_zone_4': activity.get('powerTimeInZone_4'),
                'power_time_in_zone_5': activity.get('powerTimeInZone_5'),
                'power_time_in_zone_6': activity.get('powerTimeInZone_6'),
                'power_time_in_zone_7': activity.get('powerTimeInZone_7'),
                'average_biking_cadence_rpm': activity.get('averageBikingCadenceInRevPerMinute'),
                'max_biking_cadence_rpm': activity.get('maxBikingCadenceInRevPerMinute'),
                'aerobic_training_effect': activity.get('aerobicTrainingEffect'),
                'anaerobic_training_effect': activity.get('anaerobicTrainingEffect'),
                'training_effect_label': activity.get('trainingEffectLabel'),
                'aerobic_training_effect_message': activity.get('aerobicTrainingEffectMessage'),
                'anaerobic_training_effect_message': activity.get('anaerobicTrainingEffectMessage'),
                'activity_training_load': activity.get('activityTrainingLoad'),
                'moderate_intensity_minutes': activity.get('moderateIntensityMinutes'),
                'vigorous_intensity_minutes': activity.get('vigorousIntensityMinutes'),
                'calories': activity.get('calories'),
                'device_id': activity.get('deviceId'),
                'manufacturer': activity.get('manufacturer'),
                'has_polyline': activity.get('hasPolyline', False),
                'has_images': activity.get('hasImages', False),
                'has_video': activity.get('hasVideo', False),
                'has_heat_map': activity.get('hasHeatMap', False),
                'has_splits': activity.get('hasSplits', False),
                'manual_activity': activity.get('manualActivity', False),
                'auto_calc_calories': activity.get('autoCalcCalories', False),
                'elevation_corrected': activity.get('elevationCorrected', False),
                'atp_activity': activity.get('atpActivity', False),
                'favorite': activity.get('favorite', False),
                'pr': activity.get('pr', False),
                'purposeful': activity.get('purposeful', False),
                'qualifying_dive': activity.get('qualifyingDive', False),
                'deco_dive': activity.get('decoDive', False),
                'parent': activity.get('parent', False),
                'lap_count': activity.get('lapCount'),
                'privacy_type_id': privacy.get('typeId'),
                'privacy_type_key': privacy.get('typeKey'),
                'strokes': activity.get('strokes'),
                'created_at': now,
                'updated_at': now,
                'synced_at': now
            }
            
            # Build the INSERT statement dynamically
            columns = ', '.join(activity_data.keys())
            placeholders = ', '.join(['?' for _ in activity_data])
            values = tuple(activity_data.values())
            
            cursor.execute(f"""
                INSERT OR REPLACE INTO activities ({columns})
                VALUES ({placeholders})
            """, values)
            
            # Insert user roles if present
            user_roles = activity.get('userRoles', [])
            if user_roles and activity.get('ownerId'):
                for role in user_roles:
                    cursor.execute("""
                        INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)
                    """, (activity.get('ownerId'), role))
            
            conn.commit()
            return exists  # True if activity was updated, False if new
            
        except sqlite3.Error as e:
            print(f"❌ Database error inserting activity {activity.get('activityId', 'unknown')}: {e}")
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def print_summary(self):
        """Print a summary of activities in the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM activities")
        total_count = cursor.fetchone()[0]
        
        cursor.execute("""
            SELECT activity_type_key, COUNT(*) 
            FROM activities 
            WHERE activity_type_key IS NOT NULL
            GROUP BY activity_type_key 
            ORDER BY COUNT(*) DESC
        """)
        type_counts = cursor.fetchall()
        
        cursor.execute("""
            SELECT 
                MIN(start_time_local) as earliest,
                MAX(start_time_local) as latest
            FROM activities 
            WHERE start_time_local IS NOT NULL
        """)
        date_range = cursor.fetchone()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as with_power,
                AVG(avg_power) as avg_power,
                MAX(max_power) as max_power
            FROM activities 
            WHERE avg_power IS NOT NULL AND avg_power > 0
        """)
        power_stats = cursor.fetchone()
        
        cursor.execute("""
            SELECT 
                COUNT(*) as with_hr,
                AVG(average_hr) as avg_hr,
                MAX(max_hr) as max_hr
            FROM activities 
            WHERE average_hr IS NOT NULL AND average_hr > 0
        """)
        hr_stats = cursor.fetchone()
        
        conn.close()
        
        print(f"\n{'='*60}")
        print(f"GARMIN CONNECT ACTIVITIES SUMMARY")
        print(f"{'='*60}")
        print(f"📊 Total activities: {total_count}")
        
        if type_counts:
            print(f"\n🏃 Activities by type:")
            for activity_type, count in type_counts:
                print(f"  {activity_type}: {count}")
        
        if date_range and date_range[0] and date_range[1]:
            print(f"\n📅 Date range: {date_range[0]} to {date_range[1]}")
        
        if power_stats and power_stats[0]:
            print(f"\n⚡ Power data:")
            print(f"  Activities with power: {power_stats[0]}")
            print(f"  Average power: {power_stats[1]:.1f}W" if power_stats[1] else "  Average power: N/A")
            print(f"  Max power: {power_stats[2]:.0f}W" if power_stats[2] else "  Max power: N/A")
        
        if hr_stats and hr_stats[0]:
            print(f"\n❤️  Heart rate data:")
            print(f"  Activities with HR: {hr_stats[0]}")
            print(f"  Average HR: {hr_stats[1]:.0f} bpm" if hr_stats[1] else "  Average HR: N/A")
            print(f"  Max HR: {hr_stats[2]:.0f} bpm" if hr_stats[2] else "  Max HR: N/A")
        
        self._print_health_coverage()

        print(f"\n💾 Database: {self.db_path}")

    def _print_health_coverage(self):
        """
        Report row counts for every health dataset, calling out empty ones.

        An endpoint that fails on every run leaves its table empty, which is
        otherwise invisible — the per-run warning scrolls past and the data is
        simply never there. Listing empty datasets here makes that obvious.
        """
        health_tables = [
            'daily_sleep', 'daily_stress', 'daily_hrv', 'daily_steps',
            'daily_hydration', 'daily_intensity_minutes', 'body_composition',
            'daily_body_battery', 'daily_heart_rate', 'daily_respiration',
            'daily_spo2', 'daily_floors', 'training_readiness',
            'training_status', 'blood_pressure', 'daily_max_metrics',
            'fitness_age', 'race_predictions', 'endurance_score',
            'hill_score', 'devices',
        ]

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        populated, empty = [], []
        for table in health_tables:
            try:
                n = cursor.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            except sqlite3.Error:
                continue
            (populated if n else empty).append((table, n))
        conn.close()

        print(f"\n🩺 Health data coverage:")
        for table, n in populated:
            print(f"  {table:28s} {n:>6} rows")

        if empty:
            print(f"\n⚠️  Empty datasets — these synced nothing:")
            for table, _ in empty:
                print(f"  {table}")
            print("  If a dataset should have data, re-run and check the warning")
            print("  printed for it above; the endpoint is likely failing.")

    def download_all_activities(self):
        """Download every activity — download_activities already pages."""
        print("📥 Starting to download ALL Garmin Connect activities...")
        total = self.download_activities(limit=10**9, days_back=None)
        print(f"🎉 Total activities downloaded: {total}")
        return total

    # =========================================================================
    # Health & Wellness Data Download Methods
    # =========================================================================

    def _get_date_range(self, days_back=None):
        """Get start/end dates from config or CLI override."""
        if days_back is not None:
            start = date.today() - timedelta(days=days_back)
        else:
            start_date_str = os.getenv('GARMIN_START_DATE')
            if start_date_str:
                start = datetime.strptime(start_date_str, '%Y-%m-%d').date()
            else:
                start = (datetime.now() - timedelta(days=730)).date()
        end = date.today()
        return start, end

    def _upsert(self, table, data, pk='calendar_date'):
        """Generic upsert helper for health data."""
        if not data:
            return
        conn = sqlite3.connect(self.db_path)
        try:
            columns = ', '.join(data.keys())
            placeholders = ', '.join(['?' for _ in data])
            conn.execute(
                f"INSERT OR REPLACE INTO {table} ({columns}) VALUES ({placeholders})",
                tuple(data.values())
            )
            conn.commit()
        finally:
            conn.close()

    def _attempt(self, fn, arg, failures):
        """
        Run fn(arg), retrying once after a pause if Garmin rate-limits.

        A failure is counted rather than raised so one bad day or chunk never
        aborts the sync — but counted, and summarised by the caller, because
        swallowing it silently makes a broken endpoint look identical to "no
        data recorded", which is how a dataset can quietly stay empty forever.
        Returns what fn returned, or None on failure.
        """
        for attempt in (0, 1):
            try:
                return fn(arg)
            except Exception as e:
                err = str(e)
                if attempt == 0 and ('429' in err or 'Too Many' in err):
                    print("  ⏳ Rate limited, waiting 60s...")
                    time.sleep(60)
                    continue
                failures[err[:120]] = failures.get(err[:120], 0) + 1
                return None

    @staticmethod
    def _report(label, count, unit, failures, total):
        print(f"  ✅ {label}: {count} {unit} synced")
        if failures:
            skipped = sum(failures.values())
            print(f"  ⚠️  {label}: {skipped}/{total} requests failed. Most common reasons:")
            for msg, n in sorted(failures.items(), key=lambda kv: -kv[1])[:3]:
                print(f"       ({n}×) {msg}")

    def _day_by_day(self, label, start, end, fetch_fn):
        """Call fetch_fn(day) for each day; it returns True when it stored a row."""
        current, count, failures = start, 0, {}
        total = (end - start).days + 1
        while current <= end:
            if self._attempt(fetch_fn, current, failures):
                count += 1
                if count % 50 == 0:
                    print(f"  📝 {label}: {count} days...")
            current += timedelta(days=1)
            time.sleep(0.1)  # Be gentle with the API
        self._report(label, count, "days", failures, total)

    def _ranged(self, label, start, end, fetch_fn, chunk_days=RANGE_CHUNK_DAYS, unit="days"):
        """Call fetch_fn((chunk_start, chunk_end)) per chunk; it returns rows stored."""
        chunks = []
        while start <= end:
            chunk_end = min(start + timedelta(days=chunk_days - 1), end)
            chunks.append((start, chunk_end))
            start = chunk_end + timedelta(days=1)
        count, failures = 0, {}
        for chunk in chunks:
            count += self._attempt(fetch_fn, chunk, failures) or 0
            time.sleep(0.1)
        self._report(label, count, unit, failures, len(chunks))

    def download_health_data(self, days_back=None):
        """
        Download health and wellness data over the Personal API.

        Not everything the Connect web API had is offered: training readiness,
        training status, max metrics, race predictions, endurance/hill score,
        blood pressure and devices all answer 404 on the Personal API. Their
        tables keep what was synced before and are no longer written.
        """
        start, end = self._get_date_range(days_back=days_back)
        days = (end - start).days + 1
        print(f"\n📥 Downloading health data from {start} to {end} ({days} days)...")

        # Range queries
        self._download_daily_summaries(start, end)
        self._download_daily_hrv(start, end)
        self._download_sleep_data(start, end)
        self._download_body_composition(start, end)

        # Day by day — kept for the intraday series stored in raw_json
        self._download_heart_rate(start, end)
        self._download_spo2(start, end)
        self._download_fitness_age(start, end)

        print(f"\n🎉 Health data download complete!")

    # -- Range queries --

    def _download_daily_summaries(self, start, end):
        """
        One v2 daily summary per day feeds seven tables: steps, stress,
        intensity minutes, floors, respiration, hydration, and the stress
        levels daily_body_battery has always carried.

        Six months per call worked and a year did not, so 90-day chunks.
        A section that is empty — a day the watch was not worn — writes
        nothing, rather than a row of nulls over whatever is already there.
        """
        print(f"  📊 Downloading daily summaries...")

        def fetch(chunk):
            body = garmin_api.get('/usersummary-service/v2/dailysummaries',
                                  params={'startDate': str(chunk[0]), 'endDate': str(chunk[1])})
            rows = 0
            for day in (body or {}).get('data') or []:
                rows += self._store_daily_summary(day)
            return rows

        self._ranged("Daily summaries", start, end, fetch, chunk_days=90, unit="rows")

    def _store_daily_summary(self, day):
        """Write one v2 daily summary into the tables it covers. Returns rows written."""
        d = day.get('calendarDate')
        if not d:
            return 0
        rows = 0
        movement = day.get('movement') or {}
        steps = movement.get('steps') or {}
        stress = day.get('stress') or {}
        im = day.get('intensityMinutes') or {}
        up, down = movement.get('floorsAscended') or {}, movement.get('floorsDescended') or {}
        resp = day.get('respiration') or {}
        hyd = day.get('hydration') or {}
        bb = day.get('bodyBattery') or {}

        def ms_to_s(v):
            return v // 1000 if v is not None else None

        if steps.get('value') is not None:
            self._upsert('daily_steps', {
                'calendar_date': d,
                'total_steps': steps.get('value'),
                'total_distance': steps.get('distanceInMeters'),
                'step_goal': steps.get('goal'),
            }); rows += 1
        if stress.get('avgLevel') is not None:
            self._upsert('daily_stress', {
                'calendar_date': d,
                'overall_stress_level': stress.get('avgLevel'),
                'rest_stress_duration': ms_to_s(stress.get('restDurationInMillis')),
                'low_stress_duration': ms_to_s(stress.get('lowStressDurationInMillis')),
                'medium_stress_duration': ms_to_s(stress.get('mediumStressDurationInMillis')),
                'high_stress_duration': ms_to_s(stress.get('highStressDurationInMillis')),
            }); rows += 1
        if im.get('moderate') is not None or im.get('vigorous') is not None:
            self._upsert('daily_intensity_minutes', {
                'calendar_date': d,
                'weekly_goal': im.get('goal'),
                'moderate_value': im.get('moderate'),
                'vigorous_value': im.get('vigorous'),
            }); rows += 1
        if up.get('value') is not None:
            self._upsert('daily_floors', {
                'calendar_date': d,
                'total_floors': up.get('value'),
                'floor_goal': up.get('goal'),
                'raw_json': json.dumps({'floorsAscended': up, 'floorsDescended': down}),
            }); rows += 1
        if resp.get('avgValue') is not None:
            self._upsert('daily_respiration', {
                'calendar_date': d,
                'avg_waking_respiration': resp.get('avgValue'),
                'highest_respiration': resp.get('maxValue'),
                'lowest_respiration': resp.get('minValue'),
                'raw_json': json.dumps(resp),
            }); rows += 1
        # Garmin reports 0 consumed for every day nobody logged a drink.
        if hyd.get('consumedInFractionalMl'):
            self._upsert('daily_hydration', {
                'calendar_date': d,
                'value_in_ml': hyd.get('consumedInFractionalMl'),
                'goal_in_ml': hyd.get('goalInFractionalMl'),
            }); rows += 1
        if bb or stress.get('maxLevel') is not None:
            self._upsert('daily_body_battery', {
                'calendar_date': d,
                'max_stress_level': stress.get('maxLevel'),
                'avg_stress_level': stress.get('avgLevel'),
                'raw_json': json.dumps(bb),
            }); rows += 1
        return rows

    def _download_daily_hrv(self, start, end):
        print(f"  📊 Downloading daily HRV...")

        def fetch(chunk):
            body = garmin_api.get(f'/hrv-service/hrv/daily/{chunk[0]}/{chunk[1]}')
            rows = 0
            for hrv in (body or {}).get('hrvSummaries') or []:
                baseline = hrv.get('baseline') or {}
                self._upsert('daily_hrv', {
                    'calendar_date': hrv.get('calendarDate'),
                    'weekly_avg': hrv.get('weeklyAvg'),
                    'last_night_avg': hrv.get('lastNightAvg'),
                    'last_night_5_min_high': hrv.get('lastNight5MinHigh'),
                    'baseline_low_upper': baseline.get('lowUpper'),
                    'baseline_balanced_low': baseline.get('balancedLow'),
                    'baseline_balanced_upper': baseline.get('balancedUpper'),
                    'baseline_marker_value': baseline.get('markerValue'),
                    'status': hrv.get('status'),
                    'feedback_phrase': hrv.get('feedbackPhrase'),
                })
                rows += 1
            return rows

        self._ranged("Daily HRV", start, end, fetch)

    def _download_sleep_data(self, start, end):
        print(f"  📊 Downloading sleep data...")

        def score(scores, key):
            return (scores.get(key) or {}).get('value')

        def fetch(chunk):
            body = garmin_api.get('/sleep-service/sleep/dailySleepSummariesByDate',
                                  params={'startDate': str(chunk[0]), 'endDate': str(chunk[1])})
            rows = 0
            for dto in body or []:
                if not dto.get('calendarDate') or dto.get('sleepTimeSeconds') is None:
                    continue
                scores = dto.get('sleepScores') or {}
                self._upsert('daily_sleep', {
                    'calendar_date': dto.get('calendarDate'),
                    'sleep_time_seconds': dto.get('sleepTimeSeconds'),
                    'nap_time_seconds': dto.get('napTimeSeconds'),
                    'deep_sleep_seconds': dto.get('deepSleepSeconds'),
                    'light_sleep_seconds': dto.get('lightSleepSeconds'),
                    'rem_sleep_seconds': dto.get('remSleepSeconds'),
                    'awake_sleep_seconds': dto.get('awakeSleepSeconds'),
                    'unmeasurable_sleep_seconds': dto.get('unmeasurableSleepSeconds'),
                    'sleep_start_timestamp_gmt': dto.get('sleepStartTimestampGMT'),
                    'sleep_end_timestamp_gmt': dto.get('sleepEndTimestampGMT'),
                    'sleep_start_timestamp_local': dto.get('sleepStartTimestampLocal'),
                    'sleep_end_timestamp_local': dto.get('sleepEndTimestampLocal'),
                    'device_rem_capable': dto.get('deviceRemCapable'),
                    'sleep_score_overall': score(scores, 'overall'),
                    'sleep_score_total_duration': score(scores, 'totalDuration'),
                    'sleep_score_stress': score(scores, 'stress'),
                    'sleep_score_awake_count': score(scores, 'awakeCount'),
                    'sleep_score_rem_percentage': score(scores, 'remPercentage'),
                    'sleep_score_restlessness': score(scores, 'restlessness'),
                    'sleep_score_light_percentage': score(scores, 'lightPercentage'),
                    'sleep_score_deep_percentage': score(scores, 'deepPercentage'),
                    'average_spo2': dto.get('averageSpO2Value'),
                    'lowest_spo2': dto.get('lowestSpO2Value'),
                    'highest_spo2': dto.get('highestSpO2Value'),
                    'average_spo2_hr_sleep': dto.get('averageSpO2HRSleep'),
                    'average_respiration': dto.get('averageRespirationValue'),
                    'lowest_respiration': dto.get('lowestRespirationValue'),
                    'highest_respiration': dto.get('highestRespirationValue'),
                    'avg_sleep_stress': dto.get('avgSleepStress'),
                    'sleep_score_feedback': dto.get('sleepScoreFeedback'),
                    'sleep_score_insight': dto.get('sleepScoreInsight'),
                })
                rows += 1
            return rows

        self._ranged("Sleep data", start, end, fetch)

    def _download_body_composition(self, start, end):
        print(f"  📊 Downloading body composition...")

        def fetch(chunk):
            body = garmin_api.get(f'/weight-service/weight/range/{chunk[0]}/{chunk[1]}',
                                  params={'includeAll': 'true'})
            rows = 0
            for summary in (body or {}).get('dailyWeightSummaries') or []:
                for entry in summary.get('allWeightMetrics') or []:
                    if entry.get('timestampGMT') is None:
                        continue  # skip entries with no timestamp
                    self._upsert('body_composition', {
                        'sample_pk': entry.get('samplePk'),
                        'calendar_date': entry.get('calendarDate'),
                        'weight': entry.get('weight'),
                        'bmi': entry.get('bmi'),
                        'body_fat': entry.get('bodyFat'),
                        'body_water': entry.get('bodyWater'),
                        'bone_mass': entry.get('boneMass'),
                        'muscle_mass': entry.get('muscleMass'),
                        'physique_rating': entry.get('physiqueRating'),
                        'visceral_fat': entry.get('visceralFat'),
                        'metabolic_age': entry.get('metabolicAge'),
                        'source_type': entry.get('sourceType'),
                        'timestamp_gmt': entry.get('timestampGMT'),
                    })
                    rows += 1
            return rows

        self._ranged("Body composition", start, end, fetch, chunk_days=90, unit="entries")

    # -- Day by day --

    def _download_heart_rate(self, start, end):
        print(f"  📊 Downloading heart rate...")
        def fetch(d):
            data = garmin_api.get('/wellness-service/wellness/dailyHeartRate',
                                  params={'date': str(d)})
            if not data or (data.get('restingHeartRate') is None
                            and data.get('maxHeartRate') is None):
                return False
            self._upsert('daily_heart_rate', {
                'calendar_date': str(d),
                'resting_heart_rate': data.get('restingHeartRate'),
                'max_heart_rate': data.get('maxHeartRate'),
                'min_heart_rate': data.get('minHeartRate'),
                'raw_json': json.dumps(data),
            })
            return True
        self._day_by_day("Heart rate", start, end, fetch)

    def _download_spo2(self, start, end):
        # The Personal API serves SpO2 as spo2acclimation; the plain
        # /daily/spo2 path 404s. Same top-level fields.
        print(f"  📊 Downloading SpO2...")
        def fetch(d):
            data = garmin_api.get(f'/wellness-service/wellness/daily/spo2acclimation/{d}')
            if not data or (data.get('averageSpO2') is None
                            and data.get('lowestSpO2') is None):
                return False
            self._upsert('daily_spo2', {
                'calendar_date': str(d),
                'avg_spo2': data.get('averageSpO2'),
                'lowest_spo2': data.get('lowestSpO2'),
                'latest_spo2': data.get('latestSpO2'),
                'raw_json': json.dumps(data),
            })
            return True
        self._day_by_day("SpO2", start, end, fetch)

    def _download_fitness_age(self, start, end):
        print(f"  📊 Downloading fitness age...")
        def fetch(d):
            data = garmin_api.get(f'/fitnessage-service/fitnessage/v2/{d}')
            if not data or data.get('fitnessAge') is None:
                return False
            self._upsert('fitness_age', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
            return True
        self._day_by_day("Fitness age", start, end, fetch)


def main():
    """Main function to run the Garmin Connect downloader."""
    parser = argparse.ArgumentParser(description='Garmin Connect Activities & Health Data Downloader')
    parser.add_argument('--days', type=int, default=None,
                        help='Number of days back from today to sync (overrides GARMIN_START_DATE)')
    args = parser.parse_args()

    print("🏃 Garmin Connect Activities Downloader")
    print("Using the Garmin Personal API")
    print("=" * 50)

    try:
        downloader = GarminConnectDownloader()

        # Download activities
        count = downloader.download_activities(days_back=args.days)

        # Download health & wellness data
        downloader.download_health_data(days_back=args.days)

        # Show summary
        downloader.print_summary()

        print(f"\n✅ Successfully processed {count} activities + health data!")

    except Exception as e:
        print(f"❌ Error: {e}")
        return 1

    return 0

if __name__ == "__main__":
    exit(main())