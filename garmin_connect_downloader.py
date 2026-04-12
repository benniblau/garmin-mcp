#!/usr/bin/env python3
"""
Garmin Connect Activities Downloader

A clean implementation using garth for authentication with MFA support.
Downloads activities and inserts them into a database schema that matches
the actual Garmin Connect API response structure.

Author: Generated with Claude Code
"""

import argparse
import json
import os
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from typing import Dict, Any, List
from dotenv import load_dotenv

# Import garth for Garmin authentication
try:
    import garth
    print("✅ Garth library loaded successfully")
except ImportError as e:
    print(f"❌ Missing required library: {e}")
    print("Please install: pip install garth")
    exit(1)

# Load environment variables
load_dotenv()

class GarminConnectDownloader:
    """Garmin Connect activity downloader using garth authentication."""

    def __init__(self, db_path: str = os.getenv('DB_PATH')):
        self.db_path = db_path
        self.init_database()
        self.authenticate()
    
    def init_database(self):
        """Initialize the SQLite database with the Garmin schema."""
        print(f"Initializing Garmin database: {self.db_path}")
        
        # Create the database schema based on garmin_activity_schema.json
        schema_sql = """
        -- Main activities table matching Garmin API structure
        CREATE TABLE IF NOT EXISTS activities (
            -- Primary identifiers
            activity_id BIGINT PRIMARY KEY,
            activity_name TEXT NOT NULL,
            
            -- Timing
            start_time_local TEXT,
            start_time_gmt TEXT,
            end_time_gmt TEXT,
            begin_timestamp BIGINT,
            
            -- Activity classification
            activity_type_id INTEGER,
            activity_type_key TEXT,
            activity_type_parent_id INTEGER,
            activity_type_is_hidden BOOLEAN,
            activity_type_restricted BOOLEAN,
            activity_type_trimmable BOOLEAN,
            
            sport_type_id INTEGER,
            event_type_id INTEGER,
            event_type_key TEXT,
            event_type_sort_order INTEGER,
            
            -- Duration (seconds)
            duration REAL,
            elapsed_duration REAL,
            moving_duration REAL,
            min_activity_lap_duration REAL,
            
            -- Distance and elevation
            distance REAL, -- meters
            elevation_gain REAL, -- meters
            elevation_loss REAL, -- meters
            min_elevation REAL, -- meters
            max_elevation REAL, -- meters
            max_vertical_speed REAL, -- m/s
            
            -- Speed
            average_speed REAL, -- m/s
            max_speed REAL, -- m/s
            
            -- Location
            start_latitude REAL,
            start_longitude REAL,
            end_latitude REAL,
            end_longitude REAL,
            time_zone_id INTEGER,
            
            -- Owner/Athlete info
            owner_id BIGINT,
            owner_display_name TEXT,
            owner_full_name TEXT,
            owner_profile_image_small TEXT,
            owner_profile_image_medium TEXT,
            owner_profile_image_large TEXT,
            user_pro BOOLEAN DEFAULT FALSE,
            
            -- Heart rate
            average_hr REAL,
            max_hr REAL,
            hr_time_in_zone_1 REAL,
            hr_time_in_zone_2 REAL,
            hr_time_in_zone_3 REAL,
            hr_time_in_zone_4 REAL,
            hr_time_in_zone_5 REAL,
            
            -- Power data
            avg_power REAL,
            max_power REAL,
            norm_power REAL,
            max_20min_power REAL,
            max_avg_power_1 INTEGER,
            max_avg_power_2 INTEGER,
            max_avg_power_5 INTEGER,
            max_avg_power_10 INTEGER,
            max_avg_power_20 INTEGER,
            max_avg_power_30 INTEGER,
            max_avg_power_60 INTEGER,
            max_avg_power_120 INTEGER,
            max_avg_power_300 INTEGER,
            max_avg_power_600 INTEGER,
            max_avg_power_1200 INTEGER,
            max_avg_power_1800 INTEGER,
            exclude_from_power_curve_reports BOOLEAN DEFAULT FALSE,
            
            -- Power zones
            power_time_in_zone_1 REAL,
            power_time_in_zone_2 REAL,
            power_time_in_zone_3 REAL,
            power_time_in_zone_4 REAL,
            power_time_in_zone_5 REAL,
            power_time_in_zone_6 REAL,
            power_time_in_zone_7 REAL,
            
            -- Cadence
            average_biking_cadence_rpm REAL,
            max_biking_cadence_rpm REAL,
            
            -- Training effects
            aerobic_training_effect REAL,
            anaerobic_training_effect REAL,
            training_effect_label TEXT,
            aerobic_training_effect_message TEXT,
            anaerobic_training_effect_message TEXT,
            activity_training_load REAL,
            
            -- Intensity minutes
            moderate_intensity_minutes INTEGER,
            vigorous_intensity_minutes INTEGER,
            
            -- Energy
            calories REAL,
            
            -- Device info
            device_id BIGINT,
            manufacturer TEXT,
            
            -- Activity flags
            has_polyline BOOLEAN DEFAULT FALSE,
            has_images BOOLEAN DEFAULT FALSE,
            has_video BOOLEAN DEFAULT FALSE,
            has_heat_map BOOLEAN DEFAULT FALSE,
            has_splits BOOLEAN DEFAULT FALSE,
            manual_activity BOOLEAN DEFAULT FALSE,
            auto_calc_calories BOOLEAN DEFAULT FALSE,
            elevation_corrected BOOLEAN DEFAULT FALSE,
            atp_activity BOOLEAN DEFAULT FALSE,
            favorite BOOLEAN DEFAULT FALSE,
            pr BOOLEAN DEFAULT FALSE,
            purposeful BOOLEAN DEFAULT FALSE,
            qualifying_dive BOOLEAN DEFAULT FALSE,
            deco_dive BOOLEAN DEFAULT FALSE,
            parent BOOLEAN DEFAULT FALSE,
            
            -- Lap info
            lap_count INTEGER,
            
            -- Privacy
            privacy_type_id INTEGER,
            privacy_type_key TEXT,
            
            -- Other metrics
            strokes REAL,
            
            -- Metadata
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now')),
            synced_at TEXT DEFAULT (datetime('now'))
        );
        
        -- User roles table
        CREATE TABLE IF NOT EXISTS user_roles (
            user_id BIGINT,
            role TEXT,
            created_at TEXT DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, role)
        );
        
        -- Indexes for performance
        CREATE INDEX IF NOT EXISTS idx_activities_owner ON activities(owner_id);
        CREATE INDEX IF NOT EXISTS idx_activities_start_time ON activities(start_time_local);
        CREATE INDEX IF NOT EXISTS idx_activities_activity_type ON activities(activity_type_key);
        CREATE INDEX IF NOT EXISTS idx_activities_sport_type ON activities(sport_type_id);
        CREATE INDEX IF NOT EXISTS idx_activities_distance ON activities(distance);
        CREATE INDEX IF NOT EXISTS idx_activities_duration ON activities(duration);
        CREATE INDEX IF NOT EXISTS idx_activities_created ON activities(created_at);

        -- Health & Wellness tables
        CREATE TABLE IF NOT EXISTS daily_sleep (
            calendar_date TEXT PRIMARY KEY,
            sleep_time_seconds INTEGER, nap_time_seconds INTEGER,
            deep_sleep_seconds INTEGER, light_sleep_seconds INTEGER,
            rem_sleep_seconds INTEGER, awake_sleep_seconds INTEGER,
            unmeasurable_sleep_seconds INTEGER,
            sleep_start_timestamp_gmt BIGINT, sleep_end_timestamp_gmt BIGINT,
            sleep_start_timestamp_local BIGINT, sleep_end_timestamp_local BIGINT,
            device_rem_capable BOOLEAN,
            sleep_score_overall INTEGER, sleep_score_total_duration INTEGER,
            sleep_score_stress INTEGER, sleep_score_awake_count INTEGER,
            sleep_score_rem_percentage INTEGER, sleep_score_restlessness INTEGER,
            sleep_score_light_percentage INTEGER, sleep_score_deep_percentage INTEGER,
            average_spo2 REAL, lowest_spo2 INTEGER, highest_spo2 INTEGER,
            average_spo2_hr_sleep REAL,
            average_respiration REAL, lowest_respiration REAL, highest_respiration REAL,
            avg_sleep_stress REAL,
            sleep_score_feedback TEXT, sleep_score_insight TEXT,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_stress (
            calendar_date TEXT PRIMARY KEY,
            overall_stress_level INTEGER,
            rest_stress_duration INTEGER, low_stress_duration INTEGER,
            medium_stress_duration INTEGER, high_stress_duration INTEGER,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_hrv (
            calendar_date TEXT PRIMARY KEY,
            weekly_avg INTEGER, last_night_avg INTEGER, last_night_5_min_high INTEGER,
            baseline_low_upper INTEGER, baseline_balanced_low INTEGER,
            baseline_balanced_upper INTEGER, baseline_marker_value REAL,
            status TEXT, feedback_phrase TEXT,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_steps (
            calendar_date TEXT PRIMARY KEY,
            total_steps INTEGER, total_distance INTEGER, step_goal INTEGER,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_hydration (
            calendar_date TEXT PRIMARY KEY,
            value_in_ml REAL, goal_in_ml REAL,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_intensity_minutes (
            calendar_date TEXT PRIMARY KEY,
            weekly_goal INTEGER, moderate_value INTEGER, vigorous_value INTEGER,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS body_composition (
            sample_pk INTEGER PRIMARY KEY,
            calendar_date TEXT, weight REAL, bmi REAL, body_fat REAL,
            body_water REAL, bone_mass INTEGER, muscle_mass INTEGER,
            physique_rating REAL, visceral_fat REAL, metabolic_age INTEGER,
            source_type TEXT, timestamp_gmt BIGINT,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_body_battery (
            calendar_date TEXT PRIMARY KEY,
            max_stress_level INTEGER, avg_stress_level INTEGER,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_heart_rate (
            calendar_date TEXT PRIMARY KEY,
            resting_heart_rate INTEGER, max_heart_rate INTEGER, min_heart_rate INTEGER,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_respiration (
            calendar_date TEXT PRIMARY KEY,
            avg_waking_respiration REAL, highest_respiration REAL, lowest_respiration REAL,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_spo2 (
            calendar_date TEXT PRIMARY KEY,
            avg_spo2 REAL, lowest_spo2 REAL, latest_spo2 REAL,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_floors (
            calendar_date TEXT PRIMARY KEY,
            total_floors INTEGER, floor_goal INTEGER,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS training_readiness (
            calendar_date TEXT PRIMARY KEY,
            score INTEGER, level TEXT,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS training_status (
            calendar_date TEXT PRIMARY KEY,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS blood_pressure (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            calendar_date TEXT, systolic INTEGER, diastolic INTEGER,
            pulse INTEGER, timestamp_gmt TEXT, notes TEXT, source_type TEXT,
            synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS daily_max_metrics (
            calendar_date TEXT PRIMARY KEY,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS fitness_age (
            calendar_date TEXT PRIMARY KEY,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS race_predictions (
            calendar_date TEXT PRIMARY KEY,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS endurance_score (
            calendar_date TEXT PRIMARY KEY,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS hill_score (
            calendar_date TEXT PRIMARY KEY,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS devices (
            device_id BIGINT PRIMARY KEY,
            device_name TEXT, device_type TEXT,
            raw_json TEXT, synced_at TEXT DEFAULT (datetime('now'))
        );
        CREATE INDEX IF NOT EXISTS idx_body_composition_date ON body_composition(calendar_date);
        CREATE INDEX IF NOT EXISTS idx_blood_pressure_date ON blood_pressure(calendar_date);
        """
        
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()
            
            # Execute the schema
            cursor.executescript(schema_sql)
            
            conn.commit()
            conn.close()
            print("✅ Garmin database initialized successfully")
            
        except sqlite3.Error as e:
            print(f"❌ Database error: {e}")
            raise
    
    def authenticate(self):
        """Authenticate with Garmin Connect using garth."""
        email = os.getenv('GARMIN_EMAIL')
        password = os.getenv('GARMIN_PASSWORD')

        if not email or not password:
            print("❌ Please set GARMIN_EMAIL and GARMIN_PASSWORD in .env file")
            raise ValueError("Missing Garmin credentials")

        session_path = os.getenv('GARTH_SESSION_PATH', '.garth')
        # Ensure the session directory exists so garth.save() can write to it
        os.makedirs(session_path, exist_ok=True)

        print("🔐 Authenticating with Garmin Connect...")

        try:
            # Try to resume existing session first (only if token files are present)
            token_file = os.path.join(session_path, 'oauth1_token.json')
            if os.path.exists(token_file):
                try:
                    garth.resume(session_path)
                    print("✅ Resumed existing Garmin session")

                    # Test the connection with a simple API call
                    try:
                        # Use activities endpoint instead of problematic userprofile endpoint
                        activities = garth.connectapi('/activitylist-service/activities/search/activities', params={'limit': 1})
                        print("✅ Session valid - Connection test successful")
                        return
                    except Exception as test_error:
                        print(f"⚠️  Session expired: {test_error}")
                        # Continue to fresh login

                except Exception as resume_error:
                    print(f"⚠️  Could not resume session: {resume_error}")
            else:
                print(f"⚠️  No saved session found at {session_path!r} — performing fresh login.")
                print("    Tip: run the downloader locally once, then copy the session directory to production.")

            # Fresh login with MFA support — retry on 429 with exponential backoff
            print("🔑 Performing fresh Garmin login (MFA supported)...")
            max_attempts = 3
            for attempt in range(1, max_attempts + 1):
                try:
                    garth.login(email, password)
                    break
                except Exception as login_err:
                    err_str = str(login_err)
                    if '429' in err_str and attempt < max_attempts:
                        wait = 30 * (2 ** (attempt - 1))  # 30s, 60s
                        print(f"⚠️  Rate limited (429) — waiting {wait}s before retry {attempt + 1}/{max_attempts}...")
                        time.sleep(wait)
                    else:
                        raise

            # Save the session for future use
            garth.save(session_path)
            print("✅ Session saved successfully")

            # Test the new session
            activities = garth.connectapi('/activitylist-service/activities/search/activities', params={'limit': 1})
            print("✅ Authentication successful - Connection test passed")

        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            raise
    
    def download_activities(self, limit: int = os.getenv('GARMIN_LIMIT'), start: int = 0, days_back=None):
        """Download activities from Garmin Connect using garth API."""

        # Determine start date: CLI --days overrides env var
        start_date = None
        if days_back is not None:
            start_date = datetime.now() - timedelta(days=days_back)
            print(f"📥 Downloading activities from last {days_back} days (limit: {limit})...")
        else:
            start_date_str = os.getenv('GARMIN_START_DATE')
            if start_date_str:
                try:
                    start_date = datetime.strptime(start_date_str, '%Y-%m-%d')
                    print(f"📥 Downloading activities from {start_date_str} onwards (limit: {limit}, start: {start})...")
                except ValueError:
                    print(f"⚠️  Invalid GARMIN_START_DATE format '{start_date_str}'. Expected YYYY-MM-DD. Using default.")
                    start_date = None
            else:
                print(f"📥 Downloading up to {limit} activities (starting from {start})...")
                start_date = None
        
        try:
            # Build API parameters (Note: startDate parameter is not supported by this endpoint)
            params = {'limit': limit, 'start': start}
            
            # Use garth to call the activities API directly
            activities = garth.connectapi(
                '/activitylist-service/activities/search/activities',
                params=params
            )
            
            if not activities:
                print("📭 No activities found!")
                return 0
            
            # Filter activities by start date if specified
            if start_date:
                filtered_activities = []
                for activity in activities:
                    # Parse the activity start time
                    activity_start_str = activity.get('startTimeLocal') or activity.get('startTimeGMT')
                    if activity_start_str:
                        try:
                            # Parse the activity date (format: YYYY-MM-DD HH:MM:SS)
                            activity_start = datetime.strptime(activity_start_str[:10], '%Y-%m-%d')
                            if activity_start >= start_date:
                                filtered_activities.append(activity)
                        except ValueError:
                            # If we can't parse the date, include the activity
                            filtered_activities.append(activity)
                    else:
                        # If no start time, include the activity
                        filtered_activities.append(activity)
                
                activities = filtered_activities
                print(f"📊 Found {len(activities)} activities after date filtering")
            else:
                print(f"📊 Found {len(activities)} activities")
            
            if not activities:
                print("📭 No activities match the date filter!")
                return 0
            
            inserted_count = 0
            updated_count = 0
            
            for i, activity in enumerate(activities):
                try:
                    was_updated = self.insert_activity(activity)
                    if was_updated:
                        updated_count += 1
                    else:
                        inserted_count += 1
                    
                    if (i + 1) % 10 == 0:
                        print(f"📝 Processed {i + 1}/{len(activities)} activities...")
                        
                except Exception as e:
                    print(f"⚠️  Error processing activity {activity.get('activityId', 'unknown')}: {e}")
                    continue
            
            print(f"✅ Successfully processed {len(activities)} activities")
            print(f"   📊 New activities: {inserted_count}")
            print(f"   🔄 Updated activities: {updated_count}")
            return len(activities)
            
        except Exception as e:
            print(f"❌ Error downloading activities: {e}")
            raise
    
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
        
        print(f"\n💾 Database: {self.db_path}")
    
    def download_all_activities(self, batch_size: int = 100):
        """Download all activities in batches."""
        print("📥 Starting to download ALL Garmin Connect activities...")
        
        total_downloaded = 0
        start = 0
        
        while True:
            try:
                count = self.download_activities(limit=batch_size, start=start)
                
                if count == 0:
                    print("✅ No more activities to download")
                    break
                
                total_downloaded += count
                start += batch_size
                
                print(f"📊 Downloaded {total_downloaded} activities so far...")
                
                # If we got fewer than the batch size, we're done
                if count < batch_size:
                    print("✅ Reached end of activities")
                    break
                    
            except Exception as e:
                print(f"❌ Error during batch download: {e}")
                break
        
        print(f"🎉 Total activities downloaded: {total_downloaded}")
        return total_downloaded

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

    def _get_display_name(self):
        """Get the Garmin display name for API calls that require it."""
        if not hasattr(self, '_display_name'):
            try:
                profile = garth.connectapi('/userprofile-service/socialProfile')
                self._display_name = profile.get('displayName', '')
            except Exception:
                self._display_name = ''
        return self._display_name

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

    def _day_by_day(self, label, start, end, fetch_fn):
        """Iterate day-by-day, calling fetch_fn(current_date) for each day."""
        current = start
        count = 0
        total = (end - start).days + 1
        while current <= end:
            try:
                fetch_fn(current)
                count += 1
            except Exception as e:
                err = str(e)
                if '429' in err or 'Too Many' in err:
                    print(f"  ⏳ Rate limited, waiting 60s...")
                    time.sleep(60)
                    try:
                        fetch_fn(current)
                        count += 1
                    except Exception:
                        pass
                # Silently skip days with no data
            if count % 50 == 0 and count > 0:
                print(f"  📝 {label}: {count}/{total} days...")
            current += timedelta(days=1)
            time.sleep(0.1)  # Be gentle with the API
        print(f"  ✅ {label}: {count} days synced")

    def download_health_data(self, days_back=None):
        """Download all health and wellness data."""
        start, end = self._get_date_range(days_back=days_back)
        days = (end - start).days + 1
        print(f"\n📥 Downloading health data from {start} to {end} ({days} days)...")

        # --- Garth Stats (bulk range queries) ---
        self._download_daily_steps(start, end, days)
        self._download_daily_stress(start, end, days)
        self._download_daily_hrv(start, end, days)
        self._download_daily_hydration(start, end, days)
        self._download_daily_intensity_minutes(start, end, days)

        # --- Garth Data (day-by-day) ---
        self._download_sleep_data(start, end)
        self._download_body_composition(start, end, days)
        self._download_body_battery(start, end)

        # --- Garmin Connect API (day-by-day) ---
        self._download_heart_rate(start, end)
        self._download_respiration(start, end)
        self._download_spo2(start, end)
        self._download_floors(start, end)
        self._download_training_readiness(start, end)
        self._download_training_status(start, end)
        self._download_max_metrics(start, end)
        self._download_fitness_age(start, end)
        self._download_endurance_score(start, end)
        self._download_hill_score(start, end)
        self._download_race_predictions(start, end)
        self._download_blood_pressure(start, end)
        self._download_devices()

        print(f"\n🎉 Health data download complete!")

    # -- Garth Stats methods (bulk) --

    def _download_daily_steps(self, start, end, days):
        from garth.stats import DailySteps
        print(f"  📊 Downloading daily steps...")
        try:
            items = DailySteps.list(end, period=days)
            for item in items:
                self._upsert('daily_steps', {
                    'calendar_date': str(item.calendar_date),
                    'total_steps': item.total_steps,
                    'total_distance': item.total_distance,
                    'step_goal': item.step_goal,
                })
            print(f"  ✅ Daily steps: {len(items)} days synced")
        except Exception as e:
            print(f"  ⚠️ Daily steps failed: {e}")

    def _download_daily_stress(self, start, end, days):
        from garth.stats import DailyStress
        print(f"  📊 Downloading daily stress...")
        try:
            items = DailyStress.list(end, period=days)
            for item in items:
                self._upsert('daily_stress', {
                    'calendar_date': str(item.calendar_date),
                    'overall_stress_level': item.overall_stress_level,
                    'rest_stress_duration': item.rest_stress_duration,
                    'low_stress_duration': item.low_stress_duration,
                    'medium_stress_duration': item.medium_stress_duration,
                    'high_stress_duration': item.high_stress_duration,
                })
            print(f"  ✅ Daily stress: {len(items)} days synced")
        except Exception as e:
            print(f"  ⚠️ Daily stress failed: {e}")

    def _download_daily_hrv(self, start, end, days):
        from garth.stats import DailyHRV
        print(f"  📊 Downloading daily HRV...")
        try:
            items = DailyHRV.list(end, period=days)
            for item in items:
                baseline = item.baseline
                self._upsert('daily_hrv', {
                    'calendar_date': str(item.calendar_date),
                    'weekly_avg': item.weekly_avg,
                    'last_night_avg': item.last_night_avg,
                    'last_night_5_min_high': item.last_night_5_min_high,
                    'baseline_low_upper': baseline.low_upper if baseline else None,
                    'baseline_balanced_low': baseline.balanced_low if baseline else None,
                    'baseline_balanced_upper': baseline.balanced_upper if baseline else None,
                    'baseline_marker_value': baseline.marker_value if baseline else None,
                    'status': item.status,
                    'feedback_phrase': item.feedback_phrase,
                })
            print(f"  ✅ Daily HRV: {len(items)} days synced")
        except Exception as e:
            print(f"  ⚠️ Daily HRV failed: {e}")

    def _download_daily_hydration(self, start, end, days):
        from garth.stats import DailyHydration
        print(f"  📊 Downloading daily hydration...")
        try:
            items = DailyHydration.list(end, period=days)
            for item in items:
                self._upsert('daily_hydration', {
                    'calendar_date': str(item.calendar_date),
                    'value_in_ml': item.value_in_ml,
                    'goal_in_ml': item.goal_in_ml,
                })
            print(f"  ✅ Daily hydration: {len(items)} days synced")
        except Exception as e:
            print(f"  ⚠️ Daily hydration failed: {e}")

    def _download_daily_intensity_minutes(self, start, end, days):
        from garth.stats import DailyIntensityMinutes
        print(f"  📊 Downloading daily intensity minutes...")
        try:
            items = DailyIntensityMinutes.list(end, period=days)
            for item in items:
                self._upsert('daily_intensity_minutes', {
                    'calendar_date': str(item.calendar_date),
                    'weekly_goal': item.weekly_goal,
                    'moderate_value': item.moderate_value,
                    'vigorous_value': item.vigorous_value,
                })
            print(f"  ✅ Daily intensity minutes: {len(items)} days synced")
        except Exception as e:
            print(f"  ⚠️ Daily intensity minutes failed: {e}")

    # -- Garth Data methods (day-by-day) --

    def _download_sleep_data(self, start, end):
        from garth.data import SleepData
        print(f"  📊 Downloading sleep data...")
        def fetch(d):
            sleep = SleepData.get(d)
            if sleep is None:
                return
            dto = sleep.daily_sleep_dto
            scores = dto.sleep_scores
            self._upsert('daily_sleep', {
                'calendar_date': str(dto.calendar_date),
                'sleep_time_seconds': dto.sleep_time_seconds,
                'nap_time_seconds': dto.nap_time_seconds,
                'deep_sleep_seconds': dto.deep_sleep_seconds,
                'light_sleep_seconds': dto.light_sleep_seconds,
                'rem_sleep_seconds': dto.rem_sleep_seconds,
                'awake_sleep_seconds': dto.awake_sleep_seconds,
                'unmeasurable_sleep_seconds': dto.unmeasurable_sleep_seconds,
                'sleep_start_timestamp_gmt': dto.sleep_start_timestamp_gmt,
                'sleep_end_timestamp_gmt': dto.sleep_end_timestamp_gmt,
                'sleep_start_timestamp_local': dto.sleep_start_timestamp_local,
                'sleep_end_timestamp_local': dto.sleep_end_timestamp_local,
                'device_rem_capable': dto.device_rem_capable,
                'sleep_score_overall': scores.overall.value if scores and scores.overall else None,
                'sleep_score_total_duration': scores.total_duration.value if scores and scores.total_duration else None,
                'sleep_score_stress': scores.stress.value if scores and scores.stress else None,
                'sleep_score_awake_count': scores.awake_count.value if scores and scores.awake_count else None,
                'sleep_score_rem_percentage': scores.rem_percentage.value if scores and scores.rem_percentage else None,
                'sleep_score_restlessness': scores.restlessness.value if scores and scores.restlessness else None,
                'sleep_score_light_percentage': scores.light_percentage.value if scores and scores.light_percentage else None,
                'sleep_score_deep_percentage': scores.deep_percentage.value if scores and scores.deep_percentage else None,
                'average_spo2': dto.average_sp_o2_value,
                'lowest_spo2': dto.lowest_sp_o2_value,
                'highest_spo2': dto.highest_sp_o2_value,
                'average_spo2_hr_sleep': dto.average_sp_o2_hr_sleep,
                'average_respiration': dto.average_respiration_value,
                'lowest_respiration': dto.lowest_respiration_value,
                'highest_respiration': dto.highest_respiration_value,
                'avg_sleep_stress': dto.avg_sleep_stress,
                'sleep_score_feedback': dto.sleep_score_feedback,
                'sleep_score_insight': dto.sleep_score_insight,
            })
        self._day_by_day("Sleep data", start, end, fetch)

    def _download_body_composition(self, start, end, days):
        from garth.data import WeightData
        print(f"  📊 Downloading body composition...")
        try:
            items = WeightData.list(end, days=days)
            for item in items:
                self._upsert('body_composition', {
                    'sample_pk': item.sample_pk,
                    'calendar_date': str(item.calendar_date),
                    'weight': item.weight,
                    'bmi': item.bmi,
                    'body_fat': item.body_fat,
                    'body_water': item.body_water,
                    'bone_mass': item.bone_mass,
                    'muscle_mass': item.muscle_mass,
                    'physique_rating': item.physique_rating,
                    'visceral_fat': item.visceral_fat,
                    'metabolic_age': item.metabolic_age,
                    'source_type': item.source_type,
                    'timestamp_gmt': item.timestamp_gmt,
                })
            print(f"  ✅ Body composition: {len(items)} entries synced")
        except Exception as e:
            print(f"  ⚠️ Body composition failed: {e}")

    def _download_body_battery(self, start, end):
        from garth.data.body_battery import DailyBodyBatteryStress
        print(f"  📊 Downloading body battery...")
        def fetch(d):
            data = DailyBodyBatteryStress.get(d)
            if data is None:
                return
            self._upsert('daily_body_battery', {
                'calendar_date': str(data.calendar_date),
                'max_stress_level': data.max_stress_level,
                'avg_stress_level': data.avg_stress_level,
                'raw_json': json.dumps({
                    'stress_chart_value_offset': data.stress_chart_value_offset,
                    'stress_chart_y_axis_origin': data.stress_chart_y_axis_origin,
                }),
            })
        self._day_by_day("Body battery", start, end, fetch)

    # -- Garmin Connect API methods (day-by-day raw) --

    def _download_heart_rate(self, start, end):
        display_name = self._get_display_name()
        print(f"  📊 Downloading heart rate...")
        def fetch(d):
            data = garth.connectapi(
                f'/wellness-service/wellness/dailyHeartRate/{display_name}',
                params={'date': str(d)}
            )
            if not data:
                return
            self._upsert('daily_heart_rate', {
                'calendar_date': str(d),
                'resting_heart_rate': data.get('restingHeartRate'),
                'max_heart_rate': data.get('maxHeartRate'),
                'min_heart_rate': data.get('minHeartRate'),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Heart rate", start, end, fetch)

    def _download_respiration(self, start, end):
        print(f"  📊 Downloading respiration...")
        def fetch(d):
            data = garth.connectapi(f'/wellness-service/wellness/daily/respiration/{d}')
            if not data:
                return
            self._upsert('daily_respiration', {
                'calendar_date': str(d),
                'avg_waking_respiration': data.get('avgWakingRespirationValue'),
                'highest_respiration': data.get('highestRespirationValue'),
                'lowest_respiration': data.get('lowestRespirationValue'),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Respiration", start, end, fetch)

    def _download_spo2(self, start, end):
        print(f"  📊 Downloading SpO2...")
        def fetch(d):
            data = garth.connectapi(f'/wellness-service/wellness/daily/spo2/{d}')
            if not data:
                return
            self._upsert('daily_spo2', {
                'calendar_date': str(d),
                'avg_spo2': data.get('averageSpO2'),
                'lowest_spo2': data.get('lowestSpO2'),
                'latest_spo2': data.get('latestSpO2'),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("SpO2", start, end, fetch)

    def _download_floors(self, start, end):
        print(f"  📊 Downloading floors...")
        def fetch(d):
            data = garth.connectapi(f'/wellness-service/wellness/floorsChartData/daily/{d}')
            if not data:
                return
            # Floors endpoint returns a list of floor entries
            total = sum(entry.get('floorsAscended', 0) for entry in data) if isinstance(data, list) else 0
            goal = data[0].get('floorGoal') if isinstance(data, list) and data else None
            self._upsert('daily_floors', {
                'calendar_date': str(d),
                'total_floors': total,
                'floor_goal': goal,
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Floors", start, end, fetch)

    def _download_training_readiness(self, start, end):
        print(f"  📊 Downloading training readiness...")
        def fetch(d):
            data = garth.connectapi(f'/metrics-service/metrics/trainingreadiness/{d}')
            if not data:
                return
            self._upsert('training_readiness', {
                'calendar_date': str(d),
                'score': data.get('score'),
                'level': data.get('level'),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Training readiness", start, end, fetch)

    def _download_training_status(self, start, end):
        print(f"  📊 Downloading training status...")
        def fetch(d):
            data = garth.connectapi(f'/metrics-service/metrics/trainingstatus/aggregated/{d}')
            if not data:
                return
            self._upsert('training_status', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Training status", start, end, fetch)

    def _download_max_metrics(self, start, end):
        print(f"  📊 Downloading max metrics...")
        def fetch(d):
            data = garth.connectapi(f'/metrics-service/metrics/maxmet/daily/{d}/{d}')
            if not data:
                return
            self._upsert('daily_max_metrics', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Max metrics", start, end, fetch)

    def _download_fitness_age(self, start, end):
        print(f"  📊 Downloading fitness age...")
        def fetch(d):
            data = garth.connectapi(f'/fitnessage-service/fitnessage/{d}')
            if not data:
                return
            self._upsert('fitness_age', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Fitness age", start, end, fetch)

    def _download_endurance_score(self, start, end):
        print(f"  📊 Downloading endurance score...")
        def fetch(d):
            data = garth.connectapi(
                '/metrics-service/metrics/endurancescore',
                params={'calendarDate': str(d)}
            )
            if not data:
                return
            self._upsert('endurance_score', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Endurance score", start, end, fetch)

    def _download_hill_score(self, start, end):
        print(f"  📊 Downloading hill score...")
        def fetch(d):
            data = garth.connectapi(
                '/metrics-service/metrics/hillscore',
                params={'calendarDate': str(d)}
            )
            if not data:
                return
            self._upsert('hill_score', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Hill score", start, end, fetch)

    def _download_race_predictions(self, start, end):
        display_name = self._get_display_name()
        print(f"  📊 Downloading race predictions...")
        def fetch(d):
            data = garth.connectapi(
                f'/metrics-service/metrics/racepredictions/daily/{display_name}',
                params={'fromCalendarDate': str(d), 'toCalendarDate': str(d)}
            )
            if not data:
                return
            self._upsert('race_predictions', {
                'calendar_date': str(d),
                'raw_json': json.dumps(data),
            })
        self._day_by_day("Race predictions", start, end, fetch)

    def _download_blood_pressure(self, start, end):
        print(f"  📊 Downloading blood pressure...")
        try:
            data = garth.connectapi(
                f'/bloodpressure-service/bloodpressure/range/{start}/{end}',
                params={'includeAll': 'true'}
            )
            if not data:
                print(f"  ✅ Blood pressure: no data")
                return
            readings = data if isinstance(data, list) else data.get('measurementSummaries', [])
            count = 0
            conn = sqlite3.connect(self.db_path)
            try:
                for reading in readings:
                    if isinstance(reading, dict):
                        conn.execute(
                            """INSERT OR IGNORE INTO blood_pressure
                               (calendar_date, systolic, diastolic, pulse,
                                timestamp_gmt, notes, source_type)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                reading.get('measurementTimestampLocal', '')[:10],
                                reading.get('systolic'),
                                reading.get('diastolic'),
                                reading.get('pulse'),
                                reading.get('measurementTimestampGMT'),
                                reading.get('notes'),
                                reading.get('sourceType'),
                            )
                        )
                        count += 1
                conn.commit()
            finally:
                conn.close()
            print(f"  ✅ Blood pressure: {count} readings synced")
        except Exception as e:
            print(f"  ⚠️ Blood pressure failed: {e}")

    def _download_devices(self):
        print(f"  📊 Downloading devices...")
        try:
            data = garth.connectapi('/device-service/deviceregistration/devices')
            if not data:
                print(f"  ✅ Devices: no data")
                return
            for device in data:
                self._upsert('devices', {
                    'device_id': device.get('deviceId'),
                    'device_name': device.get('displayName') or device.get('deviceName'),
                    'device_type': device.get('deviceTypeName'),
                    'raw_json': json.dumps(device),
                })
            print(f"  ✅ Devices: {len(data)} synced")
        except Exception as e:
            print(f"  ⚠️ Devices failed: {e}")


def main():
    """Main function to run the Garmin Connect downloader."""
    parser = argparse.ArgumentParser(description='Garmin Connect Activities & Health Data Downloader')
    parser.add_argument('--days', type=int, default=None,
                        help='Number of days back from today to sync (overrides GARMIN_START_DATE)')
    args = parser.parse_args()

    print("🏃 Garmin Connect Activities Downloader")
    print("Using garth authentication with MFA support")
    print("=" * 50)

    try:
        downloader = GarminConnectDownloader()

        # Download activities
        count = downloader.download_activities(
            limit=int(os.getenv('GARMIN_LIMIT')),
            days_back=args.days
        )

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