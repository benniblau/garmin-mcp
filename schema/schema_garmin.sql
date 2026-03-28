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