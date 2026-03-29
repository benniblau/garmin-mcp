#!/usr/bin/env python3
"""
MCP Server for Garmin Connect Activities Database

This server exposes the Garmin activities SQLite database to MCP clients,
providing tools and resources for querying fitness data.
"""

import argparse
import os
import sqlite3
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Literal
from contextlib import asynccontextmanager, contextmanager

from dotenv import load_dotenv
load_dotenv()

from mcp.server.fastmcp import FastMCP

# Configure logging to stderr to avoid corrupting STDIO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize the MCP server
mcp = FastMCP("garmin-activities")

# Database path - use environment variable or default
DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "garmin_activities.db")
DB_PATH = os.getenv("GARMIN_DB_PATH", DEFAULT_DB_PATH)

@contextmanager
def get_db_connection():
    """Context manager for database connections."""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Return rows as dictionaries
    try:
        yield conn
    finally:
        conn.close()

def serialize_row(row) -> Dict[str, Any]:
    """Convert SQLite row to JSON-serializable dictionary."""
    if row is None:
        return None
    return {key: row[key] for key in row.keys()}

# Resources

@mcp.resource(
    "garmin://activities",
    name="Garmin Activities",
    description="Complete collection of Garmin Connect activities",
    mime_type="application/json"
)
def resource_activities() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT * FROM activities
                ORDER BY start_time_local DESC
            """)
            activities = [serialize_row(row) for row in cursor.fetchall()]
            return json.dumps(activities, indent=2, default=str)
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})


@mcp.resource(
    "garmin://stats/summary",
    name="Activity Statistics Summary",
    description="Summary statistics of all activities",
    mime_type="application/json"
)
def resource_stats_summary() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    COUNT(*) as total_activities,
                    COUNT(DISTINCT activity_type_key) as unique_activity_types,
                    MIN(start_time_local) as earliest_activity,
                    MAX(start_time_local) as latest_activity,
                    SUM(distance) / 1000.0 as total_distance_km,
                    SUM(duration) / 3600.0 as total_duration_hours,
                    SUM(elevation_gain) as total_elevation_gain_m,
                    SUM(calories) as total_calories,
                    AVG(average_hr) as avg_heart_rate,
                    AVG(avg_power) as avg_power,
                    COUNT(CASE WHEN avg_power > 0 THEN 1 END) as activities_with_power,
                    COUNT(CASE WHEN average_hr > 0 THEN 1 END) as activities_with_hr
                FROM activities
            """)
            stats = serialize_row(cursor.fetchone())

            cursor.execute("""
                SELECT
                    activity_type_key,
                    COUNT(*) as count,
                    SUM(distance) / 1000.0 as total_distance_km,
                    SUM(duration) / 3600.0 as total_duration_hours
                FROM activities
                WHERE activity_type_key IS NOT NULL
                GROUP BY activity_type_key
                ORDER BY count DESC
            """)
            activity_types = [serialize_row(row) for row in cursor.fetchall()]

            return json.dumps({
                "summary": stats,
                "by_activity_type": activity_types
            }, indent=2, default=str)
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})


@mcp.resource(
    "garmin://stats/monthly",
    name="Monthly Statistics",
    description="Activities grouped by month",
    mime_type="application/json"
)
def resource_stats_monthly() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT
                    strftime('%Y-%m', start_time_local) as month,
                    COUNT(*) as activity_count,
                    SUM(distance) / 1000.0 as total_distance_km,
                    SUM(duration) / 3600.0 as total_duration_hours,
                    SUM(calories) as total_calories,
                    AVG(average_hr) as avg_heart_rate
                FROM activities
                WHERE start_time_local IS NOT NULL
                GROUP BY strftime('%Y-%m', start_time_local)
                ORDER BY month DESC
                LIMIT 24
            """)
            monthly_stats = [serialize_row(row) for row in cursor.fetchall()]
            return json.dumps(monthly_stats, indent=2, default=str)
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})


@mcp.resource(
    "garmin://activities/recent",
    name="Recent Activities",
    description="Most recent activities (last 30 days)",
    mime_type="application/json"
)
def resource_activities_recent() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
            cursor.execute("""
                SELECT * FROM activities
                WHERE start_time_local >= ?
                ORDER BY start_time_local DESC
            """, (thirty_days_ago,))
            recent_activities = [serialize_row(row) for row in cursor.fetchall()]
            return json.dumps(recent_activities, indent=2, default=str)
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})


@mcp.resource(
    "garmin://health/summary",
    name="Health Data Summary",
    description="Overview of all available health data tables and their date ranges",
    mime_type="application/json"
)
def resource_health_summary() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            health_tables = [
                'daily_sleep', 'daily_stress', 'daily_hrv', 'daily_steps',
                'daily_hydration', 'daily_intensity_minutes', 'body_composition',
                'daily_body_battery', 'daily_heart_rate', 'daily_respiration',
                'daily_spo2', 'daily_floors', 'training_readiness',
                'training_status', 'blood_pressure', 'daily_max_metrics',
                'fitness_age', 'race_predictions', 'endurance_score',
                'hill_score', 'devices'
            ]
            summary = {}
            for table in health_tables:
                try:
                    cursor.execute(f"SELECT COUNT(*) as cnt, MIN(calendar_date) as earliest, MAX(calendar_date) as latest FROM {table}")
                    row = cursor.fetchone()
                    summary[table] = {
                        "count": row['cnt'],
                        "earliest": row['earliest'],
                        "latest": row['latest']
                    }
                except Exception:
                    summary[table] = {"count": 0, "earliest": None, "latest": None}
            return json.dumps(summary, indent=2, default=str)
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})


@mcp.resource(
    "garmin://health/recent",
    name="Recent Health Snapshot",
    description="Last 7 days of key health metrics (sleep, stress, HRV, steps, heart rate, body battery)",
    mime_type="application/json"
)
def resource_health_recent() -> str:
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            seven_days_ago = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
            result = {}
            queries = {
                "sleep": "SELECT calendar_date, sleep_time_seconds/3600.0 as sleep_hours, deep_sleep_seconds/3600.0 as deep_hours, rem_sleep_seconds/3600.0 as rem_hours, sleep_score_overall, average_spo2, average_respiration FROM daily_sleep WHERE calendar_date >= ? ORDER BY calendar_date DESC",
                "stress": "SELECT * FROM daily_stress WHERE calendar_date >= ? ORDER BY calendar_date DESC",
                "hrv": "SELECT * FROM daily_hrv WHERE calendar_date >= ? ORDER BY calendar_date DESC",
                "steps": "SELECT * FROM daily_steps WHERE calendar_date >= ? ORDER BY calendar_date DESC",
                "heart_rate": "SELECT calendar_date, resting_heart_rate, max_heart_rate, min_heart_rate FROM daily_heart_rate WHERE calendar_date >= ? ORDER BY calendar_date DESC",
                "body_battery": "SELECT calendar_date, max_stress_level, avg_stress_level FROM daily_body_battery WHERE calendar_date >= ? ORDER BY calendar_date DESC",
            }
            for key, query in queries.items():
                try:
                    cursor.execute(query, (seven_days_ago,))
                    result[key] = [serialize_row(row) for row in cursor.fetchall()]
                except Exception:
                    result[key] = []
            return json.dumps(result, indent=2, default=str)
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})


# Tools

@mcp.tool()
async def query_activities(
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    min_distance: Optional[float] = None,
    max_distance: Optional[float] = None,
    min_duration: Optional[float] = None,
    has_power_data: Optional[bool] = None,
    has_hr_data: Optional[bool] = None,
    limit: int = 100,
    order_by: str = "start_time_local",
    order_desc: bool = True
) -> str:
    """Query activities with flexible filters and sorting"""

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Build WHERE clause
            conditions = []
            params = []

            if activity_type:
                conditions.append("activity_type_key = ?")
                params.append(activity_type)

            if start_date:
                conditions.append("start_time_local >= ?")
                params.append(start_date)

            if end_date:
                conditions.append("start_time_local <= ?")
                params.append(end_date)

            if min_distance is not None:
                conditions.append("distance >= ?")
                params.append(min_distance * 1000)  # Convert km to meters

            if max_distance is not None:
                conditions.append("distance <= ?")
                params.append(max_distance * 1000)  # Convert km to meters

            if min_duration is not None:
                conditions.append("duration >= ?")
                params.append(min_duration * 60)  # Convert minutes to seconds

            if has_power_data is not None:
                if has_power_data:
                    conditions.append("avg_power IS NOT NULL AND avg_power > 0")
                else:
                    conditions.append("(avg_power IS NULL OR avg_power = 0)")

            if has_hr_data is not None:
                if has_hr_data:
                    conditions.append("average_hr IS NOT NULL AND average_hr > 0")
                else:
                    conditions.append("(average_hr IS NULL OR average_hr = 0)")

            where_clause = ""
            if conditions:
                where_clause = "WHERE " + " AND ".join(conditions)

            # Build ORDER BY clause
            order_direction = "DESC" if order_desc else "ASC"

            query = f"""
                SELECT
                    activity_id, activity_name, activity_type_key,
                    start_time_local, distance/1000.0 as distance_km,
                    duration/60.0 as duration_minutes,
                    average_speed*3.6 as avg_speed_kmh,
                    elevation_gain, calories,
                    average_hr, avg_power, max_power
                FROM activities
                {where_clause}
                ORDER BY {order_by} {order_direction}
                LIMIT ?
            """

            params.append(limit)
            cursor.execute(query, params)

            results = [serialize_row(row) for row in cursor.fetchall()]

            return json.dumps({
                "query_params": {
                    "activity_type": activity_type,
                    "start_date": start_date,
                    "end_date": end_date,
                    "min_distance": min_distance,
                    "max_distance": max_distance,
                    "min_duration": min_duration,
                    "has_power_data": has_power_data,
                    "has_hr_data": has_hr_data,
                    "limit": limit,
                    "order_by": order_by,
                    "order_desc": order_desc
                },
                "results_count": len(results),
                "activities": results
            }, indent=2, default=str)

    except sqlite3.Error as e:
        logger.error(f"Database error in query_activities: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Error in query_activities: {e}")
        return json.dumps({"error": f"Query error: {str(e)}"})


@mcp.tool()
async def get_activity_details(activity_id: int) -> str:
    """Get detailed information for a specific activity by ID"""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM activities WHERE activity_id = ?", (activity_id,))
        activity = cursor.fetchone()

        if not activity:
            return json.dumps({"error": f"Activity {activity_id} not found"})

        activity_data = serialize_row(activity)

        # Add calculated fields
        if activity_data.get('distance') and activity_data.get('duration'):
            activity_data['avg_pace_min_per_km'] = (activity_data['duration'] / 60) / (activity_data['distance'] / 1000)

        return json.dumps(activity_data, indent=2, default=str)


@mcp.tool()
async def get_power_analysis(
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
) -> str:
    """Get power analysis for activities with power data"""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Build WHERE clause
        conditions = ["avg_power IS NOT NULL AND avg_power > 0"]
        params = []

        if activity_type:
            conditions.append("activity_type_key = ?")
            params.append(activity_type)

        if start_date:
            conditions.append("start_time_local >= ?")
            params.append(start_date)

        if end_date:
            conditions.append("start_time_local <= ?")
            params.append(end_date)

        where_clause = "WHERE " + " AND ".join(conditions)

        # Get power statistics
        cursor.execute(f"""
            SELECT
                COUNT(*) as activities_with_power,
                AVG(avg_power) as avg_power_overall,
                MAX(max_power) as max_power_overall,
                AVG(norm_power) as avg_normalized_power,
                AVG(max_20min_power) as avg_ftp_estimate,
                MAX(max_20min_power) as best_20min_power
            FROM activities
            {where_clause}
        """, params)

        power_stats = serialize_row(cursor.fetchone())

        # Get recent power activities
        cursor.execute(f"""
            SELECT
                activity_id, activity_name, start_time_local,
                avg_power, max_power, norm_power, max_20min_power,
                duration/60.0 as duration_minutes,
                activity_training_load
            FROM activities
            {where_clause}
            ORDER BY start_time_local DESC
            LIMIT ?
        """, params + [limit])

        power_activities = [serialize_row(row) for row in cursor.fetchall()]

        return json.dumps({
            "power_statistics": power_stats,
            "recent_power_activities": power_activities
        }, indent=2, default=str)


@mcp.tool()
async def get_training_trends(
    period: str = "month",
    activity_type: Optional[str] = None,
    metric: str = "distance",
    limit: int = 12
) -> str:
    """Analyze training trends over time periods"""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Map period to SQLite date format
        period_formats = {
            "week": "%Y-%W",
            "month": "%Y-%m",
            "quarter": "%Y-Q" + str(((datetime.now().month - 1) // 3) + 1)
        }

        date_format = period_formats.get(period, "%Y-%m")

        # Map metric to SQL expression
        metric_expressions = {
            "distance": "SUM(distance) / 1000.0",
            "duration": "SUM(duration) / 3600.0",
            "avg_power": "AVG(avg_power)",
            "avg_hr": "AVG(average_hr)"
        }

        metric_expr = metric_expressions.get(metric, "SUM(distance) / 1000.0")

        # Build WHERE clause
        conditions = ["start_time_local IS NOT NULL"]
        params = []

        if activity_type:
            conditions.append("activity_type_key = ?")
            params.append(activity_type)

        where_clause = "WHERE " + " AND ".join(conditions)

        cursor.execute(f"""
            SELECT
                strftime('{date_format}', start_time_local) as period,
                COUNT(*) as activity_count,
                {metric_expr} as metric_value,
                SUM(calories) as total_calories
            FROM activities
            {where_clause}
            GROUP BY strftime('{date_format}', start_time_local)
            ORDER BY period DESC
            LIMIT ?
        """, params + [limit])

        trends = [serialize_row(row) for row in cursor.fetchall()]

        return json.dumps({
            "analysis_params": {
                "period": period,
                "activity_type": activity_type,
                "metric": metric,
                "limit": limit
            },
            "trends": trends
        }, indent=2, default=str)


@mcp.tool()
async def execute_sql(query: str, limit: int = 1000) -> str:
    """Execute custom SQL query on the activities database. Available health tables: daily_sleep, daily_stress, daily_hrv, daily_steps, daily_hydration, daily_intensity_minutes, body_composition, daily_body_battery, daily_heart_rate, daily_respiration, daily_spo2, daily_floors, training_readiness, training_status, blood_pressure, daily_max_metrics, fitness_age, race_predictions, endurance_score, hill_score, devices. Use the daily_health_summary view for a combined overview."""

    # Security check - only allow SELECT queries
    query_trimmed = query.strip().upper()
    if not query_trimmed.startswith("SELECT"):
        return json.dumps({"error": "Only SELECT queries are allowed"})

    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()

            # Add LIMIT if not present
            if "LIMIT" not in query_trimmed:
                query += f" LIMIT {limit}"

            cursor.execute(query)
            results = [serialize_row(row) for row in cursor.fetchall()]

            return json.dumps({
                "query": query,
                "results_count": len(results),
                "results": results
            }, indent=2, default=str)

    except sqlite3.Error as e:
        return json.dumps({"error": f"SQL Error: {str(e)}"})


@mcp.tool()
async def get_daily_health_summary(
    date: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30
) -> str:
    """Get a combined daily health summary for a specific date or date range, joining sleep, stress, HRV, steps, heart rate, body battery, hydration, and intensity minutes"""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        conditions = []
        params = []

        if date:
            conditions.append("s.calendar_date = ?")
            params.append(date)
        else:
            if start_date:
                conditions.append("s.calendar_date >= ?")
                params.append(start_date)
            if end_date:
                conditions.append("s.calendar_date <= ?")
                params.append(end_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(f"""
            SELECT
                s.calendar_date,
                s.total_steps, s.step_goal,
                st.overall_stress_level,
                st.rest_stress_duration, st.low_stress_duration,
                st.medium_stress_duration, st.high_stress_duration,
                h.last_night_avg as hrv_last_night,
                h.weekly_avg as hrv_weekly_avg,
                h.status as hrv_status,
                sl.sleep_time_seconds / 3600.0 as sleep_hours,
                sl.deep_sleep_seconds / 3600.0 as deep_sleep_hours,
                sl.light_sleep_seconds / 3600.0 as light_sleep_hours,
                sl.rem_sleep_seconds / 3600.0 as rem_sleep_hours,
                sl.sleep_score_overall,
                sl.average_spo2 as sleep_avg_spo2,
                sl.average_respiration as sleep_avg_respiration,
                bb.max_stress_level as bb_max_stress,
                bb.avg_stress_level as bb_avg_stress,
                hr.resting_heart_rate, hr.max_heart_rate, hr.min_heart_rate,
                im.moderate_value as moderate_intensity_min,
                im.vigorous_value as vigorous_intensity_min,
                hy.value_in_ml as hydration_ml,
                hy.goal_in_ml as hydration_goal_ml,
                fl.total_floors, fl.floor_goal,
                r.avg_waking_respiration, r.highest_respiration, r.lowest_respiration,
                sp.avg_spo2, sp.lowest_spo2
            FROM daily_steps s
            LEFT JOIN daily_stress st ON s.calendar_date = st.calendar_date
            LEFT JOIN daily_hrv h ON s.calendar_date = h.calendar_date
            LEFT JOIN daily_sleep sl ON s.calendar_date = sl.calendar_date
            LEFT JOIN daily_body_battery bb ON s.calendar_date = bb.calendar_date
            LEFT JOIN daily_heart_rate hr ON s.calendar_date = hr.calendar_date
            LEFT JOIN daily_intensity_minutes im ON s.calendar_date = im.calendar_date
            LEFT JOIN daily_hydration hy ON s.calendar_date = hy.calendar_date
            LEFT JOIN daily_floors fl ON s.calendar_date = fl.calendar_date
            LEFT JOIN daily_respiration r ON s.calendar_date = r.calendar_date
            LEFT JOIN daily_spo2 sp ON s.calendar_date = sp.calendar_date
            {where}
            ORDER BY s.calendar_date DESC
            LIMIT ?
        """, params + [limit])

        results = [serialize_row(row) for row in cursor.fetchall()]
        return json.dumps({"results_count": len(results), "daily_summaries": results}, indent=2, default=str)


@mcp.tool()
async def get_sleep_analysis(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 30
) -> str:
    """Get detailed sleep data with scores, stages, SpO2, and respiration. Supports date range filtering and trend analysis."""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        conditions = []
        params = []
        if start_date:
            conditions.append("calendar_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("calendar_date <= ?")
            params.append(end_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(f"""
            SELECT
                calendar_date,
                sleep_time_seconds / 3600.0 as total_sleep_hours,
                deep_sleep_seconds / 3600.0 as deep_sleep_hours,
                light_sleep_seconds / 3600.0 as light_sleep_hours,
                rem_sleep_seconds / 3600.0 as rem_sleep_hours,
                awake_sleep_seconds / 60.0 as awake_minutes,
                sleep_score_overall, sleep_score_total_duration,
                sleep_score_stress, sleep_score_awake_count,
                sleep_score_rem_percentage, sleep_score_restlessness,
                sleep_score_light_percentage, sleep_score_deep_percentage,
                average_spo2, lowest_spo2, highest_spo2,
                average_respiration, lowest_respiration, highest_respiration,
                avg_sleep_stress,
                sleep_score_feedback, sleep_score_insight
            FROM daily_sleep
            {where}
            ORDER BY calendar_date DESC
            LIMIT ?
        """, params + [limit])

        results = [serialize_row(row) for row in cursor.fetchall()]

        # Add summary stats
        if results:
            avg_score = sum(r['sleep_score_overall'] for r in results if r['sleep_score_overall']) / max(1, sum(1 for r in results if r['sleep_score_overall']))
            avg_hours = sum(r['total_sleep_hours'] for r in results if r['total_sleep_hours']) / max(1, sum(1 for r in results if r['total_sleep_hours']))
            summary = {
                "avg_sleep_score": round(avg_score, 1),
                "avg_sleep_hours": round(avg_hours, 2),
                "days_analyzed": len(results)
            }
        else:
            summary = {}

        return json.dumps({"summary": summary, "sleep_data": results}, indent=2, default=str)


@mcp.tool(name="get_body_composition")
async def get_body_composition_data(
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 90
) -> str:
    """Get body composition/weight data with BMI, body fat %, muscle mass, etc."""

    with get_db_connection() as conn:
        cursor = conn.cursor()

        conditions = []
        params = []
        if start_date:
            conditions.append("calendar_date >= ?")
            params.append(start_date)
        if end_date:
            conditions.append("calendar_date <= ?")
            params.append(end_date)

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

        cursor.execute(f"""
            SELECT
                calendar_date,
                weight / 1000.0 as weight_kg,
                weight / 1000.0 * 2.20462 as weight_lbs,
                bmi, body_fat, body_water,
                bone_mass / 1000.0 as bone_mass_kg,
                muscle_mass / 1000.0 as muscle_mass_kg,
                physique_rating, visceral_fat, metabolic_age,
                source_type
            FROM body_composition
            {where}
            ORDER BY calendar_date DESC
            LIMIT ?
        """, params + [limit])

        results = [serialize_row(row) for row in cursor.fetchall()]
        return json.dumps({"results_count": len(results), "body_composition": results}, indent=2, default=str)


@mcp.tool()
async def get_health_trends(
    metric: Literal["sleep_score", "sleep_hours", "resting_hr", "hrv", "stress", "steps", "body_fat", "weight"],
    period: Literal["week", "month"] = "week",
    limit: int = 12
) -> str:
    """Get health metric trends over time. Supports weekly or monthly aggregation of any health metric."""

    metric_config = {
        "sleep_score": ("daily_sleep", "AVG(sleep_score_overall)", "avg_sleep_score"),
        "sleep_hours": ("daily_sleep", "AVG(sleep_time_seconds / 3600.0)", "avg_sleep_hours"),
        "resting_hr": ("daily_heart_rate", "AVG(resting_heart_rate)", "avg_resting_hr"),
        "hrv": ("daily_hrv", "AVG(last_night_avg)", "avg_hrv"),
        "stress": ("daily_stress", "AVG(overall_stress_level)", "avg_stress"),
        "steps": ("daily_steps", "AVG(total_steps)", "avg_steps"),
        "body_fat": ("body_composition", "AVG(body_fat)", "avg_body_fat"),
        "weight": ("body_composition", "AVG(weight / 1000.0)", "avg_weight_kg"),
    }

    if metric not in metric_config:
        return json.dumps({"error": f"Unknown metric: {metric}"})

    table, expr, alias = metric_config[metric]
    date_format = "%Y-%W" if period == "week" else "%Y-%m"

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            SELECT
                strftime('{date_format}', calendar_date) as period,
                {expr} as {alias},
                COUNT(*) as data_points
            FROM {table}
            WHERE calendar_date IS NOT NULL
            GROUP BY strftime('{date_format}', calendar_date)
            ORDER BY period DESC
            LIMIT ?
        """, (limit,))

        results = [serialize_row(row) for row in cursor.fetchall()]
        return json.dumps({
            "metric": metric,
            "period": period,
            "trends": results
        }, indent=2, default=str)


def run_stdio():
    """Run the MCP server over STDIO transport."""
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        logger.error("Please ensure the Garmin activities database exists.")
        return
    mcp.run()


def main_http():
    """Run the MCP server over Streamable HTTP transport with bearer token auth."""
    import uvicorn
    from starlette.applications import Starlette
    from starlette.middleware import Middleware
    from starlette.middleware.authentication import AuthenticationMiddleware
    from starlette.routing import Mount

    from mcp.server.auth.middleware.bearer_auth import BearerAuthBackend, RequireAuthMiddleware
    from mcp.server.auth.provider import AccessToken
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager

    # Verify database exists
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        logger.error("Please ensure the Garmin activities database exists.")
        return

    # Read config
    auth_token = os.getenv("GARMIN_MCP_AUTH_TOKEN")
    if not auth_token:
        logger.error("GARMIN_MCP_AUTH_TOKEN environment variable is required for HTTP transport")
        sys.exit(1)

    host = os.getenv("GARMIN_MCP_HTTP_HOST", "0.0.0.0")
    port = int(os.getenv("GARMIN_MCP_HTTP_PORT", "8080"))

    # Static bearer token verifier
    class StaticTokenVerifier:
        def __init__(self, expected_token: str):
            self.expected_token = expected_token

        async def verify_token(self, token: str) -> AccessToken | None:
            if token == self.expected_token:
                return AccessToken(
                    token=token,
                    client_id="static",
                    scopes=["mcp:access"],
                    expires_at=None,
                )
            return None

    verifier = StaticTokenVerifier(auth_token)
    session_manager = StreamableHTTPSessionManager(app=mcp._mcp_server, stateless=True)

    @asynccontextmanager
    async def lifespan(app):
        async with session_manager.run():
            yield

    mcp_app = RequireAuthMiddleware(
        session_manager.handle_request,
        required_scopes=["mcp:access"],
    )

    app = Starlette(
        routes=[
            Mount("/mcp", app=mcp_app),
        ],
        middleware=[
            Middleware(AuthenticationMiddleware, backend=BearerAuthBackend(verifier)),
        ],
        lifespan=lifespan,
    )

    logger.info(f"Starting Garmin MCP HTTP server on {host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Garmin MCP Server")
    parser.add_argument(
        "--transport",
        choices=["stdio", "http"],
        default=os.getenv("GARMIN_MCP_TRANSPORT", "stdio"),
        help="Transport mode (default: stdio, or set GARMIN_MCP_TRANSPORT env var)",
    )
    args = parser.parse_args()

    if args.transport == "http":
        main_http()
    else:
        run_stdio()
