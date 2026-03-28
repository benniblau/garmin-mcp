-- Garmin Connect Activity Database Schema
-- Designed to match the actual Garmin Connect API response structure
-- Based on garmin_activity_schema.json

-- Main activities table matching Garmin API structure
CREATE TABLE IF NOT EXISTS activities (
    -- Primary identifiers
    activity_id BIGINT PRIMARY KEY,
    activity_name TEXT NOT NULL,
    
    -- Timing
    start_time_local TIMESTAMP,
    start_time_gmt TIMESTAMP,
    end_time_gmt TIMESTAMP,
    begin_timestamp BIGINT, -- Unix timestamp
    
    -- Activity classification
    activity_type_id INTEGER,
    activity_type_key VARCHAR(50),
    activity_type_parent_id INTEGER,
    sport_type_id INTEGER,
    event_type_id INTEGER,
    event_type_key VARCHAR(50),
    
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
    owner_display_name VARCHAR(100),
    owner_full_name VARCHAR(100),
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
    training_effect_label VARCHAR(50),
    aerobic_training_effect_message VARCHAR(100),
    anaerobic_training_effect_message VARCHAR(100),
    activity_training_load REAL,
    
    -- Intensity minutes
    moderate_intensity_minutes INTEGER,
    vigorous_intensity_minutes INTEGER,
    
    -- Energy
    calories REAL,
    
    -- Device info
    device_id BIGINT,
    manufacturer VARCHAR(50),
    
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
    privacy_type_key VARCHAR(20),
    
    -- Other metrics
    strokes REAL,
    
    -- Metadata
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Activity type lookup table
CREATE TABLE IF NOT EXISTS activity_types (
    type_id INTEGER PRIMARY KEY,
    type_key VARCHAR(50) UNIQUE NOT NULL,
    parent_type_id INTEGER,
    display_name VARCHAR(100),
    is_hidden BOOLEAN DEFAULT FALSE,
    restricted BOOLEAN DEFAULT FALSE,
    trimmable BOOLEAN DEFAULT TRUE,
    
    FOREIGN KEY (parent_type_id) REFERENCES activity_types(type_id)
);

-- Event type lookup table
CREATE TABLE IF NOT EXISTS event_types (
    type_id INTEGER PRIMARY KEY,
    type_key VARCHAR(50) UNIQUE NOT NULL,
    sort_order INTEGER
);

-- User roles (from userRoles array)
CREATE TABLE IF NOT EXISTS user_roles (
    user_id BIGINT,
    role VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
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

-- Insert default activity types based on Garmin schema
INSERT INTO activity_types (type_id, type_key, parent_type_id, display_name, is_hidden, restricted, trimmable) VALUES
(152, 'virtual_ride', 2, 'Virtual Cycling', false, false, true),
(1, 'running', null, 'Running', false, false, true),
(2, 'cycling', null, 'Cycling', false, false, true),
(3, 'swimming', null, 'Swimming', false, false, true),
(4, 'walking', null, 'Walking', false, false, true),
(5, 'hiking', null, 'Hiking', false, false, true)
ON CONFLICT (type_key) DO NOTHING;

-- Insert default event types
INSERT INTO event_types (type_id, type_key, sort_order) VALUES
(9, 'uncategorized', 10),
(1, 'race', 1),
(2, 'training', 2),
(3, 'casual', 3)
ON CONFLICT (type_key) DO NOTHING;

-- =============================================================================
-- HEALTH & WELLNESS TABLES
-- =============================================================================

-- Daily sleep data (from garth SleepData)
CREATE TABLE IF NOT EXISTS daily_sleep (
    calendar_date TEXT PRIMARY KEY,
    sleep_time_seconds INTEGER,
    nap_time_seconds INTEGER,
    deep_sleep_seconds INTEGER,
    light_sleep_seconds INTEGER,
    rem_sleep_seconds INTEGER,
    awake_sleep_seconds INTEGER,
    unmeasurable_sleep_seconds INTEGER,
    sleep_start_timestamp_gmt BIGINT,
    sleep_end_timestamp_gmt BIGINT,
    sleep_start_timestamp_local BIGINT,
    sleep_end_timestamp_local BIGINT,
    device_rem_capable BOOLEAN,
    -- Sleep scores
    sleep_score_overall INTEGER,
    sleep_score_total_duration INTEGER,
    sleep_score_stress INTEGER,
    sleep_score_awake_count INTEGER,
    sleep_score_rem_percentage INTEGER,
    sleep_score_restlessness INTEGER,
    sleep_score_light_percentage INTEGER,
    sleep_score_deep_percentage INTEGER,
    -- SpO2 during sleep
    average_spo2 REAL,
    lowest_spo2 INTEGER,
    highest_spo2 INTEGER,
    average_spo2_hr_sleep REAL,
    -- Respiration during sleep
    average_respiration REAL,
    lowest_respiration REAL,
    highest_respiration REAL,
    -- Stress during sleep
    avg_sleep_stress REAL,
    sleep_score_feedback TEXT,
    sleep_score_insight TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily stress levels (from garth DailyStress)
CREATE TABLE IF NOT EXISTS daily_stress (
    calendar_date TEXT PRIMARY KEY,
    overall_stress_level INTEGER,
    rest_stress_duration INTEGER,
    low_stress_duration INTEGER,
    medium_stress_duration INTEGER,
    high_stress_duration INTEGER,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily HRV (from garth DailyHRV)
CREATE TABLE IF NOT EXISTS daily_hrv (
    calendar_date TEXT PRIMARY KEY,
    weekly_avg INTEGER,
    last_night_avg INTEGER,
    last_night_5_min_high INTEGER,
    baseline_low_upper INTEGER,
    baseline_balanced_low INTEGER,
    baseline_balanced_upper INTEGER,
    baseline_marker_value REAL,
    status TEXT,
    feedback_phrase TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily steps (from garth DailySteps)
CREATE TABLE IF NOT EXISTS daily_steps (
    calendar_date TEXT PRIMARY KEY,
    total_steps INTEGER,
    total_distance INTEGER,
    step_goal INTEGER,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily hydration (from garth DailyHydration)
CREATE TABLE IF NOT EXISTS daily_hydration (
    calendar_date TEXT PRIMARY KEY,
    value_in_ml REAL,
    goal_in_ml REAL,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily intensity minutes (from garth DailyIntensityMinutes)
CREATE TABLE IF NOT EXISTS daily_intensity_minutes (
    calendar_date TEXT PRIMARY KEY,
    weekly_goal INTEGER,
    moderate_value INTEGER,
    vigorous_value INTEGER,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Body composition / weight entries (from garth WeightData)
CREATE TABLE IF NOT EXISTS body_composition (
    sample_pk INTEGER PRIMARY KEY,
    calendar_date TEXT,
    weight REAL,
    bmi REAL,
    body_fat REAL,
    body_water REAL,
    bone_mass INTEGER,
    muscle_mass INTEGER,
    physique_rating REAL,
    visceral_fat REAL,
    metabolic_age INTEGER,
    source_type TEXT,
    timestamp_gmt BIGINT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily body battery and stress detail (from garth DailyBodyBatteryStress)
CREATE TABLE IF NOT EXISTS daily_body_battery (
    calendar_date TEXT PRIMARY KEY,
    max_stress_level INTEGER,
    avg_stress_level INTEGER,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily heart rate (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS daily_heart_rate (
    calendar_date TEXT PRIMARY KEY,
    resting_heart_rate INTEGER,
    max_heart_rate INTEGER,
    min_heart_rate INTEGER,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily respiration (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS daily_respiration (
    calendar_date TEXT PRIMARY KEY,
    avg_waking_respiration REAL,
    highest_respiration REAL,
    lowest_respiration REAL,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily SpO2 (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS daily_spo2 (
    calendar_date TEXT PRIMARY KEY,
    avg_spo2 REAL,
    lowest_spo2 REAL,
    latest_spo2 REAL,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily floors climbed (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS daily_floors (
    calendar_date TEXT PRIMARY KEY,
    total_floors INTEGER,
    floor_goal INTEGER,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Training readiness (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS training_readiness (
    calendar_date TEXT PRIMARY KEY,
    score INTEGER,
    level TEXT,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Training status (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS training_status (
    calendar_date TEXT PRIMARY KEY,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Blood pressure readings (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS blood_pressure (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    calendar_date TEXT,
    systolic INTEGER,
    diastolic INTEGER,
    pulse INTEGER,
    timestamp_gmt TEXT,
    notes TEXT,
    source_type TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Daily max metrics (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS daily_max_metrics (
    calendar_date TEXT PRIMARY KEY,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Fitness age (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS fitness_age (
    calendar_date TEXT PRIMARY KEY,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Race predictions (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS race_predictions (
    calendar_date TEXT PRIMARY KEY,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Endurance score (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS endurance_score (
    calendar_date TEXT PRIMARY KEY,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Hill score (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS hill_score (
    calendar_date TEXT PRIMARY KEY,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Registered devices (from Garmin Connect API)
CREATE TABLE IF NOT EXISTS devices (
    device_id BIGINT PRIMARY KEY,
    device_name TEXT,
    device_type TEXT,
    raw_json TEXT,
    synced_at TEXT DEFAULT (datetime('now'))
);

-- Indexes for health tables
CREATE INDEX IF NOT EXISTS idx_body_composition_date ON body_composition(calendar_date);
CREATE INDEX IF NOT EXISTS idx_blood_pressure_date ON blood_pressure(calendar_date);

-- View for daily health summary joining key metrics
CREATE VIEW IF NOT EXISTS daily_health_summary AS
SELECT
    s.calendar_date,
    s.total_steps,
    s.step_goal,
    st.overall_stress_level,
    h.last_night_avg as hrv_last_night,
    h.status as hrv_status,
    sl.sleep_time_seconds / 3600.0 as sleep_hours,
    sl.deep_sleep_seconds / 3600.0 as deep_sleep_hours,
    sl.rem_sleep_seconds / 3600.0 as rem_sleep_hours,
    sl.sleep_score_overall,
    bb.avg_stress_level as body_battery_avg_stress,
    hr.resting_heart_rate,
    im.moderate_value as moderate_intensity_min,
    im.vigorous_value as vigorous_intensity_min,
    hy.value_in_ml as hydration_ml,
    hy.goal_in_ml as hydration_goal_ml
FROM daily_steps s
LEFT JOIN daily_stress st ON s.calendar_date = st.calendar_date
LEFT JOIN daily_hrv h ON s.calendar_date = h.calendar_date
LEFT JOIN daily_sleep sl ON s.calendar_date = sl.calendar_date
LEFT JOIN daily_body_battery bb ON s.calendar_date = bb.calendar_date
LEFT JOIN daily_heart_rate hr ON s.calendar_date = hr.calendar_date
LEFT JOIN daily_intensity_minutes im ON s.calendar_date = im.calendar_date
LEFT JOIN daily_hydration hy ON s.calendar_date = hy.calendar_date
ORDER BY s.calendar_date DESC;

-- View for activity summary with calculated fields
CREATE VIEW IF NOT EXISTS activity_summary AS
SELECT 
    activity_id,
    activity_name,
    activity_type_key,
    start_time_local,
    distance / 1000.0 as distance_km,
    distance * 3.28084 / 5280.0 as distance_miles,
    duration,
    elapsed_duration,
    moving_duration,
    elevation_gain as elevation_gain_m,
    elevation_gain * 3.28084 as elevation_gain_ft,
    
    -- Speed conversions
    average_speed * 3.6 as avg_speed_kmh,
    average_speed * 2.237 as avg_speed_mph,
    
    -- Pace calculations (min/km and min/mile)
    CASE 
        WHEN average_speed > 0 THEN (1000.0 / average_speed) / 60.0 
        ELSE NULL 
    END as pace_min_per_km,
    CASE 
        WHEN average_speed > 0 THEN (1609.34 / average_speed) / 60.0 
        ELSE NULL 
    END as pace_min_per_mile,
    
    -- Performance metrics
    average_hr,
    avg_power,
    calories,
    
    -- Training metrics
    aerobic_training_effect,
    activity_training_load,
    
    -- Metadata
    created_at,
    synced_at
    
FROM activities
ORDER BY start_time_local DESC;