# Garmin Activities MCP Server

This MCP (Model Context Protocol) server exposes your Garmin Connect activities database to MCP-compatible clients, allowing you to query and analyze your fitness data through natural language interfaces.

## Features

### Resources
- **Complete Activities Collection**: Access to all stored Garmin Connect activities
- **Statistical Summaries**: Comprehensive statistics and breakdowns by activity type
- **Monthly Analytics**: Time-based activity analysis and trends  
- **Recent Activities**: Quick access to activities from the last 30 days

### Tools
- **Flexible Activity Queries**: Filter by type, date range, distance, duration, power/HR data
- **Activity Details**: Get comprehensive information for specific activities
- **Power Analysis**: Detailed power metrics analysis for cycling activities
- **Training Trends**: Analyze patterns over weeks, months, or quarters
- **Custom SQL**: Execute custom queries for advanced analysis

## Installation

1. Install dependencies:
```bash
pip install -r requirements.txt
```

2. Ensure your Garmin activities database exists:
```bash
python garmin_connect_downloader.py
```

3. Test the MCP server:
```bash
python mcp_server.py
```

## Configuration

### Environment Variables
- `GARMIN_DB_PATH`: Path to your Garmin activities SQLite database (defaults to `./garmin_activities.db`)

### Claude Desktop Integration

**Important**: Due to virtual environment isolation, you need to use the provided launcher script.

1. **Copy the configuration** to your Claude Desktop config file at:
   - macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - Windows: `%APPDATA%\Claude\claude_desktop_config.json`
   - Linux: `~/.config/Claude/claude_desktop_config.json`

2. **Use this configuration** (update paths to match your setup):

```json
{
  "mcpServers": {
    "garmin-activities": {
      "command": "/Users/benjaminblau/Documents/vscode/garmin-mcp/run_mcp_server.sh",
      "env": {
        "GARMIN_DB_PATH": "/Users/benjaminblau/Documents/vscode/garmin-mcp/garmin_activities.db"
      }
    }
  }
}
```

### Alternative Launch Methods

If the bash script doesn't work, try the Python launcher:

```json
{
  "mcpServers": {
    "garmin-activities": {
      "command": "python3",
      "args": ["/Users/benjaminblau/Documents/vscode/garmin-mcp/launcher.py"],
      "env": {
        "GARMIN_DB_PATH": "/Users/benjaminblau/Documents/vscode/garmin-mcp/garmin_activities.db"
      }
    }
  }
}
```

### Direct Virtual Environment Path

For maximum compatibility:

```json
{
  "mcpServers": {
    "garmin-activities": {
      "command": "/Users/benjaminblau/Documents/vscode/garmin-mcp/.venv/bin/python",
      "args": ["/Users/benjaminblau/Documents/vscode/garmin-mcp/mcp_server.py"],
      "env": {
        "GARMIN_DB_PATH": "/Users/benjaminblau/Documents/vscode/garmin-mcp/garmin_activities.db"
      }
    }
  }
}
```

## Usage Examples

### Query Activities
```
Find all cycling activities from the last month with power data
```

### Analyze Training
```
Show me my training trends by month for running activities
```

### Power Analysis
```
Analyze my power data for virtual rides in the last 6 months
```

### Custom Analysis
```
Execute SQL: SELECT activity_type_key, AVG(avg_power) FROM activities WHERE avg_power > 0 GROUP BY activity_type_key
```

## Available Resources

- `garmin://activities` - All activities in the database
- `garmin://stats/summary` - Comprehensive activity statistics
- `garmin://stats/monthly` - Monthly activity breakdowns  
- `garmin://activities/recent` - Recent activities (last 30 days)

## Tool Parameters

### query_activities
- `activity_type`: Filter by activity type (e.g., 'running', 'cycling', 'virtual_ride')
- `start_date`/`end_date`: Date range filters (YYYY-MM-DD format)
- `min_distance`/`max_distance`: Distance filters in kilometers
- `min_duration`: Minimum duration in minutes
- `has_power_data`/`has_hr_data`: Filter for activities with sensor data
- `limit`: Maximum results (default: 100)
- `order_by`: Sort field (start_time_local, distance, duration, avg_power)
- `order_desc`: Sort direction (default: true)

### get_power_analysis
- `activity_type`: Filter by activity type
- `start_date`/`end_date`: Date range filters
- `limit`: Maximum activities to analyze (default: 50)

### get_training_trends
- `period`: Grouping period (week, month, quarter)
- `activity_type`: Filter by activity type
- `metric`: Metric to analyze (distance, duration, avg_power, avg_hr)
- `limit`: Number of periods (default: 12)

### execute_sql
- `query`: SELECT query to execute
- `limit`: Maximum results (default: 1000)

## Database Schema

The server provides access to the complete Garmin activities schema including:
- Activity identification and timing
- Performance metrics (distance, duration, speed, elevation)
- Heart rate and power data
- Training effects and intensity zones
- Device and privacy information

See `schema_garmin.sql` for the complete database structure.

## Security

- Only SELECT queries are allowed through the `execute_sql` tool
- All database connections use read-only access
- No authentication data is exposed through the MCP interface

## Troubleshooting

1. **Database not found**: Ensure `GARMIN_DB_PATH` points to a valid SQLite database
2. **Import errors**: Install all dependencies with `pip install -r requirements.txt`
3. **Permission errors**: Check file permissions for the database file
4. **MCP connection issues**: Verify the server configuration in your MCP client