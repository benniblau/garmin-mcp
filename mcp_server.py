#!/usr/bin/env python3
"""
MCP Server for Garmin Connect Activities Database

This server exposes the Garmin activities SQLite database to MCP clients,
providing tools and resources for querying fitness data.
"""

import asyncio
import os
import sqlite3
import json
import logging
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from contextlib import contextmanager

import mcp.types as types
from mcp.server import Server
from mcp.server.models import InitializationOptions
from mcp.server import NotificationOptions
import mcp.server.stdio

# Configure logging to stderr to avoid corrupting STDIO
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize the MCP server
server = Server("garmin-activities")

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

@server.list_resources()
async def handle_list_resources() -> List[types.Resource]:
    """List available resources."""
    return [
        types.Resource(
            uri="garmin://activities",
            name="Garmin Activities",
            description="Complete collection of Garmin Connect activities",
            mimeType="application/json"
        ),
        types.Resource(
            uri="garmin://stats/summary",
            name="Activity Statistics Summary", 
            description="Summary statistics of all activities",
            mimeType="application/json"
        ),
        types.Resource(
            uri="garmin://stats/monthly",
            name="Monthly Statistics",
            description="Activities grouped by month",
            mimeType="application/json"
        ),
        types.Resource(
            uri="garmin://activities/recent",
            name="Recent Activities",
            description="Most recent activities (last 30 days)",
            mimeType="application/json"
        )
    ]

@server.read_resource()
async def handle_read_resource(uri: str) -> str:
    """Handle resource read requests."""
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            if uri == "garmin://activities":
                cursor.execute("""
                    SELECT * FROM activities 
                    ORDER BY start_time_local DESC
                """)
                activities = [serialize_row(row) for row in cursor.fetchall()]
                return json.dumps(activities, indent=2, default=str)
                
            elif uri == "garmin://stats/summary":
                # Get comprehensive statistics
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
                
                # Get activity type breakdown
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
                
            elif uri == "garmin://stats/monthly":
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
                
            elif uri == "garmin://activities/recent":
                thirty_days_ago = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d')
                cursor.execute("""
                    SELECT * FROM activities 
                    WHERE start_time_local >= ?
                    ORDER BY start_time_local DESC
                """, (thirty_days_ago,))
                recent_activities = [serialize_row(row) for row in cursor.fetchall()]
                return json.dumps(recent_activities, indent=2, default=str)
                
            else:
                raise ValueError(f"Unknown resource: {uri}")
    
    except sqlite3.Error as e:
        logger.error(f"Database error in read_resource: {e}")
        return json.dumps({"error": f"Database error: {str(e)}"})
    except Exception as e:
        logger.error(f"Unexpected error in read_resource: {e}")
        return json.dumps({"error": f"Server error: {str(e)}"})

@server.list_tools()
async def handle_list_tools() -> List[types.Tool]:
    """List available tools."""
    return [
        types.Tool(
            name="query_activities",
            description="Query activities with flexible filters and sorting",
            inputSchema={
                "type": "object",
                "properties": {
                    "activity_type": {
                        "type": "string",
                        "description": "Filter by activity type (e.g., 'running', 'cycling', 'virtual_ride')"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date filter (YYYY-MM-DD format)"
                    },
                    "end_date": {
                        "type": "string", 
                        "description": "End date filter (YYYY-MM-DD format)"
                    },
                    "min_distance": {
                        "type": "number",
                        "description": "Minimum distance in kilometers"
                    },
                    "max_distance": {
                        "type": "number",
                        "description": "Maximum distance in kilometers" 
                    },
                    "min_duration": {
                        "type": "number",
                        "description": "Minimum duration in minutes"
                    },
                    "has_power_data": {
                        "type": "boolean",
                        "description": "Filter for activities with power data"
                    },
                    "has_hr_data": {
                        "type": "boolean",
                        "description": "Filter for activities with heart rate data"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results (default: 100)",
                        "default": 100
                    },
                    "order_by": {
                        "type": "string",
                        "description": "Sort field (start_time_local, distance, duration, avg_power)",
                        "default": "start_time_local"
                    },
                    "order_desc": {
                        "type": "boolean", 
                        "description": "Sort in descending order",
                        "default": True
                    }
                }
            }
        ),
        types.Tool(
            name="get_activity_details",
            description="Get detailed information for a specific activity by ID",
            inputSchema={
                "type": "object",
                "properties": {
                    "activity_id": {
                        "type": "integer",
                        "description": "The activity ID"
                    }
                },
                "required": ["activity_id"]
            }
        ),
        types.Tool(
            name="get_power_analysis",
            description="Get power analysis for activities with power data",
            inputSchema={
                "type": "object", 
                "properties": {
                    "activity_type": {
                        "type": "string",
                        "description": "Filter by activity type"
                    },
                    "start_date": {
                        "type": "string",
                        "description": "Start date filter (YYYY-MM-DD)"
                    },
                    "end_date": {
                        "type": "string", 
                        "description": "End date filter (YYYY-MM-DD)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of activities to analyze",
                        "default": 50
                    }
                }
            }
        ),
        types.Tool(
            name="get_training_trends",
            description="Analyze training trends over time periods",
            inputSchema={
                "type": "object",
                "properties": {
                    "period": {
                        "type": "string",
                        "description": "Time period for grouping (week, month, quarter)",
                        "default": "month"
                    },
                    "activity_type": {
                        "type": "string", 
                        "description": "Filter by specific activity type"
                    },
                    "metric": {
                        "type": "string",
                        "description": "Metric to analyze (distance, duration, avg_power, avg_hr)",
                        "default": "distance"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Number of periods to return",
                        "default": 12
                    }
                }
            }
        ),
        types.Tool(
            name="execute_sql",
            description="Execute custom SQL query on the activities database",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "SQL query to execute (SELECT queries only)"
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximum number of results",
                        "default": 1000
                    }
                },
                "required": ["query"]
            }
        )
    ]

@server.call_tool()
async def handle_call_tool(name: str, arguments: Dict[str, Any]) -> List[types.TextContent]:
    """Handle tool calls."""
    try:
        logger.info(f"Calling tool: {name} with arguments: {arguments}")
        
        if name == "query_activities":
            return await query_activities(**arguments)
        elif name == "get_activity_details":
            return await get_activity_details(**arguments)
        elif name == "get_power_analysis":
            return await get_power_analysis(**arguments)
        elif name == "get_training_trends":
            return await get_training_trends(**arguments)
        elif name == "execute_sql":
            return await execute_sql(**arguments)
        else:
            logger.error(f"Unknown tool requested: {name}")
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Unknown tool: {name}"})
                )
            ]
    
    except Exception as e:
        logger.error(f"Error in tool {name}: {e}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Tool execution error: {str(e)}"})
            )
        ]

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
) -> List[types.TextContent]:
    """Query activities with flexible filters."""
    
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
            
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
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
                )
            ]
    
    except sqlite3.Error as e:
        logger.error(f"Database error in query_activities: {e}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Database error: {str(e)}"})
            )
        ]
    except Exception as e:
        logger.error(f"Error in query_activities: {e}")
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": f"Query error: {str(e)}"})
            )
        ]

async def get_activity_details(activity_id: int) -> List[types.TextContent]:
    """Get detailed information for a specific activity."""
    
    with get_db_connection() as conn:
        cursor = conn.cursor()
        
        cursor.execute("SELECT * FROM activities WHERE activity_id = ?", (activity_id,))
        activity = cursor.fetchone()
        
        if not activity:
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({"error": f"Activity {activity_id} not found"})
                )
            ]
        
        activity_data = serialize_row(activity)
        
        # Add calculated fields
        if activity_data.get('distance') and activity_data.get('duration'):
            activity_data['avg_pace_min_per_km'] = (activity_data['duration'] / 60) / (activity_data['distance'] / 1000)
            
        return [
            types.TextContent(
                type="text", 
                text=json.dumps(activity_data, indent=2, default=str)
            )
        ]

async def get_power_analysis(
    activity_type: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 50
) -> List[types.TextContent]:
    """Get power analysis for activities with power data."""
    
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
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "power_statistics": power_stats,
                    "recent_power_activities": power_activities
                }, indent=2, default=str)
            )
        ]

async def get_training_trends(
    period: str = "month",
    activity_type: Optional[str] = None,
    metric: str = "distance", 
    limit: int = 12
) -> List[types.TextContent]:
    """Analyze training trends over time periods."""
    
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
        
        return [
            types.TextContent(
                type="text",
                text=json.dumps({
                    "analysis_params": {
                        "period": period,
                        "activity_type": activity_type, 
                        "metric": metric,
                        "limit": limit
                    },
                    "trends": trends
                }, indent=2, default=str)
            )
        ]

async def execute_sql(query: str, limit: int = 1000) -> List[types.TextContent]:
    """Execute custom SQL query (SELECT only)."""
    
    # Security check - only allow SELECT queries
    query_trimmed = query.strip().upper()
    if not query_trimmed.startswith("SELECT"):
        return [
            types.TextContent(
                type="text",
                text=json.dumps({"error": "Only SELECT queries are allowed"})
            )
        ]
        
    try:
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Add LIMIT if not present
            if "LIMIT" not in query_trimmed:
                query += f" LIMIT {limit}"
                
            cursor.execute(query)
            results = [serialize_row(row) for row in cursor.fetchall()]
            
            return [
                types.TextContent(
                    type="text",
                    text=json.dumps({
                        "query": query,
                        "results_count": len(results),
                        "results": results
                    }, indent=2, default=str)
                )
            ]
            
    except sqlite3.Error as e:
        return [
            types.TextContent(
                type="text", 
                text=json.dumps({"error": f"SQL Error: {str(e)}"})
            )
        ]

async def main():
    """Run the MCP server."""
    # Verify database exists
    if not os.path.exists(DB_PATH):
        logger.error(f"Database not found at {DB_PATH}")
        logger.error("Please ensure the Garmin activities database exists.")
        return
        
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="garmin-activities",
                server_version="1.0.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={}
                )
            )
        )

if __name__ == "__main__":
    asyncio.run(main())