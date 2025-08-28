#!/usr/bin/env python3
"""
Garmin Connect Activities Downloader

A clean implementation using garth for authentication with MFA support.
Downloads activities and inserts them into a database schema that matches
the actual Garmin Connect API response structure.

Author: Generated with Claude Code
"""

import os
import sqlite3
from datetime import datetime, timezone
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
        
        print("🔐 Authenticating with Garmin Connect...")
        
        try:
            # Try to resume existing session first
            try:
                garth.resume(os.getenv('GARTH_SESSION_PATH'))
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
        
            # Fresh login with MFA support
            print("🔑 Performing fresh Garmin login (MFA supported)...")
            garth.login(email, password)
            
            # Save the session for future use
            garth.save(os.getenv('GARTH_SESSION_PATH'))
            print("✅ Session saved successfully")
            
            # Test the new session
            activities = garth.connectapi('/activitylist-service/activities/search/activities', params={'limit': 1})
            print("✅ Authentication successful - Connection test passed")
            
        except Exception as e:
            print(f"❌ Authentication failed: {e}")
            raise
    
    def download_activities(self, limit: int = os.getenv('GARMIN_LIMIT'), start: int = 0):
        """Download activities from Garmin Connect using garth API."""
        
        # Get start date from environment variable
        start_date_str = os.getenv('GARMIN_START_DATE')
        start_date = None
        if start_date_str:
            try:
                from datetime import datetime
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

def main():
    """Main function to run the Garmin Connect downloader."""
    print("🏃 Garmin Connect Activities Downloader")
    print("Using garth authentication with MFA support")
    print("=" * 50)
    
    try:
        downloader = GarminConnectDownloader()
        
        # Download recent activities (last 100)
        # For all activities, use: downloader.download_all_activities()
        count = downloader.download_activities(limit=int(os.getenv('GARMIN_LIMIT')))

        # Show summary
        downloader.print_summary()
        
        print(f"\n✅ Successfully processed {count} activities!")
        print("\n💡 To download ALL activities, use:")
        print("   downloader.download_all_activities()")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        return 1
    
    return 0

if __name__ == "__main__":
    exit(main())