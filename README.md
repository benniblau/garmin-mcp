# Garmin Connect MCP Server

A comprehensive Python application that downloads your Garmin Connect activities and exposes them through a Model Context Protocol (MCP) server for intelligent analysis and querying.

## 🏃‍♂️ What This Does

This project provides two main components:
1. **Garmin Data Downloader** - Securely downloads and stores all your Garmin Connect activities
2. **MCP Server** - Exposes your fitness data to AI assistants for natural language analysis

Perfect for athletes, fitness enthusiasts, and data analysts who want to leverage AI to understand their training patterns, performance trends, and activity insights.

## ✨ Features

### 🔄 Garmin Connect Integration
- **Secure Authentication** - MFA support with session persistence
- **Complete Activity Download** - All activities with full detail
- **Incremental Sync** - Only download new/updated activities
- **Rich Data Model** - Power, heart rate, GPS, training effects, and more

### 🗄️ SQLite Database
- **Comprehensive Schema** - 80+ activity fields matching Garmin's API
- **Performance Optimized** - Indexed for fast queries
- **Statistical Views** - Pre-calculated summaries and trends
- **Data Integrity** - Proper relationships and constraints

### 🤖 MCP Server
- **Natural Language Queries** - Ask questions about your fitness data
- **Flexible Filtering** - By activity type, date range, performance metrics
- **Statistical Analysis** - Training trends, power analysis, monthly summaries
- **Custom SQL** - Execute complex queries through AI
- **Real-time Access** - Live connection to your activity database

## 🚀 Quick Start

### 1. Setup Environment

```bash
# Clone the repository
git clone <your-repo-url>
cd garmin-mcp

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### 2. Configure Garmin Credentials

Create a `.env` file:

```env
# Garmin Connect credentials
GARMIN_EMAIL=your-email@example.com
GARMIN_PASSWORD=your-password

# Optional: Database and sync settings
GARMIN_DB_PATH=./garmin_activities.db
GARMIN_LIMIT=100
GARMIN_START_DATE=2024-01-01
GARTH_SESSION_PATH=./.garmin/session
```

### 3. Download Your Activities

```bash
# Download recent activities (default: last 100)
python garmin_connect_downloader.py

# Or download ALL activities (this may take a while!)
# Modify the main() function to use: downloader.download_all_activities()
```

### 4. Setup MCP Server

#### Option A: Local (STDIO) — for Claude Desktop

Add to your Claude Desktop configuration (`~/Library/Application Support/Claude/claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "garmin-activities": {
      "command": "/path/to/garmin-mcp/.venv/bin/python",
      "args": ["/path/to/garmin-mcp/mcp_server.py", "--transport", "stdio"],
      "env": {
        "GARMIN_DB_PATH": "/path/to/garmin-mcp/garmin_activities.db"
      }
    }
  }
}
```

#### Option B: Remote (Streamable HTTP) — for external MCP clients

Run the server in HTTP mode with bearer token authentication:

```bash
# Generate an auth token
export GARMIN_MCP_AUTH_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))")

# Start the HTTP server
python mcp_server.py --transport http
```

Connect from any MCP client using:

```json
{
  "mcpServers": {
    "garmin-activities": {
      "url": "http://your-server:8080/mcp/",
      "headers": {
        "Authorization": "Bearer <your-token>"
      }
    }
  }
}
```

See [Deployment](#-deployment) for production setup with systemd.

### REST API

HTTP mode also serves a small REST API under `/api/v1`, using the same bearer
token. It carries only what MCP cannot: MCP tools answer with text, which is
the wrong shape for a binary file. Reading activity data stays on the MCP side.

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/api/v1/health` | Liveness probe. Unauthenticated, touches nothing |
| `GET` | `/api/v1/activities/{id}/file` | The original FIT recording, as bytes |
| `GET` | `/api/v1/upload/health` | Whether the Garmin session is usable |
| `POST` | `/api/v1/upload/fit` | Import a FIT file into Garmin Connect |

```bash
# Download an activity's original recording
curl -H "Authorization: Bearer $TOKEN" -o activity.fit \
  "http://localhost:8080/api/v1/activities/24010567666/file"

# Upload a FIT file
curl -X POST -H "Authorization: Bearer $TOKEN" \
  -F "file=@activity.fit" \
  "http://localhost:8080/api/v1/upload/fit"
```

The upload body may be multipart with a `file` part, as above, or the raw bytes
with any other content type.

**Downloading.** Straight from Garmin, not from the local database — the
database holds summaries, and the point of this endpoint is the recording
itself. Garmin serves it as a ZIP wrapping the `.fit`, though some activities
come back as a bare FIT; both are unwrapped. The response carries
`X-Garmin-Sha256`. A 404 means Garmin has no such activity, and a 503 means
Garmin could not be reached — the same fetch and unwrap `export_fit.py` uses,
so the CLI and the API cannot drift apart about what Garmin actually serves.

**Uploading.** This is the one write path here, and it exists so that callers
which push activities into Garmin — [`fit-bridge`](https://github.com/benniblau/fit-bridge),
principally — do not each carry their own copy of garth, their own session file
and their own guesses about what Garmin's answer means. See `garmin_files.py`.

The answer is 200 for anything Garmin actually decided, with the verdict in
`status`:

| `status` | Meaning |
|---|---|
| `uploaded` | Garmin took it. `activity_id` and `upload_id` when reported |
| `duplicate` | Garmin already has this activity (HTTP 409, or said so in the body) |
| `failed` | Garmin refused it; `message` carries Garmin's own words |

A 4xx means the request was wrong — no file, not a FIT file, bad token. A 503
means Garmin never answered. That split is what lets a caller tell "this file
will never work" from "try again later" without parsing prose.

Note that Garmin usually answers an upload with **202 and no import result**,
so a successful upload commonly reports `uploaded` with no `activity_id`.
Resolving the activity id needs a follow-up poll of the activity list.

`/api/v1/upload/health` is separate from `/api/v1/health` because it costs a
session probe against Garmin and needs credentials, whereas `/api/v1/health`
must stay cheap enough to poll. Use it as a preflight before a batch: finding
out there that Garmin is unreachable costs nothing, whereas finding out
per-file burns a retry on every file.

## 📊 Database Schema

The SQLite database stores comprehensive activity data:

### Activities Table (Main)
```sql
activity_id             -- Primary key from Garmin
activity_name           -- Display name
start_time_local        -- Local start time
activity_type_key       -- running, cycling, virtual_ride, etc.
distance                -- Distance in meters
duration                -- Duration in seconds
average_speed           -- Speed in m/s
elevation_gain          -- Elevation gain in meters
calories                -- Energy expenditure
average_hr              -- Average heart rate
max_hr                  -- Maximum heart rate
avg_power               -- Average power (cycling)
max_power               -- Maximum power
aerobic_training_effect -- Training load metrics
-- ... 80+ more fields
```

### Supporting Tables
- `user_roles` - User permissions and roles
- `activity_summary` - Pre-calculated view with conversions (km, mph, pace)

## 🛠️ MCP Server Capabilities

### Resources
- `garmin://activities` - Complete activity collection
- `garmin://stats/summary` - Overall statistics and breakdowns
- `garmin://stats/monthly` - Monthly activity trends
- `garmin://activities/recent` - Last 30 days of activities

### Tools
- **`query_activities`** - Advanced filtering and search
- **`get_activity_details`** - Detailed individual activity data
- **`get_power_analysis`** - Cycling power metrics analysis
- **`get_training_trends`** - Time-based pattern analysis
- **`execute_sql`** - Custom database queries

### Example Queries
Once connected to Claude Desktop, you can ask:

```
"Show me my cycling activities from last month with power data"
"What are my running pace trends this year?"
"Analyze my heart rate zones for virtual rides"
"Which activities had the highest training load?"
"Compare my average power between indoor and outdoor cycling"
```

## 📈 Use Cases

### 🏋️‍♂️ Athletes & Coaches
- **Performance Analysis** - Track improvements in power, speed, endurance
- **Training Load Management** - Monitor weekly/monthly training stress
- **Recovery Insights** - Analyze heart rate patterns and training effects
- **Goal Setting** - Data-driven target setting based on historical performance

### 📊 Data Scientists
- **Trend Analysis** - Seasonal patterns, performance correlations
- **Custom Metrics** - Calculate specialized performance indicators  
- **Data Export** - JSON format for external analysis tools
- **Statistical Modeling** - Raw data access for machine learning

### 🤖 AI-Powered Insights
- **Natural Language Interface** - Ask complex questions about your fitness
- **Automated Reporting** - Generate training summaries and recommendations
- **Pattern Recognition** - Discover hidden insights in your activity data
- **Comparative Analysis** - Benchmark against your historical performance

## 🔧 Development

### Project Structure
```
garmin-mcp/
├── garmin_connect_downloader.py    # Main downloader script
├── mcp_server.py                   # MCP server (STDIO + HTTP transport, REST API)
├── garmin_files.py                 # Garmin session, FIT download and upload
├── export_fit.py                   # CLI: bulk-export originals into exports/
├── schema/
│   └── schema_garmin.sql           # Database schema (single source of truth)
├── deploy/
│   └── garmin-mcp.service          # systemd unit for production deployment
├── requirements.txt                # Python dependencies
├── .env.example                    # Environment template
└── README.md                       # This file
```

### Key Technologies
- **Authentication** - [`garth`](https://github.com/matin/garth) for Garmin Connect API
- **Database** - SQLite with comprehensive indexing
- **MCP Protocol** - Official Anthropic MCP SDK
- **Async Processing** - Full async/await support for scalability

### Testing
```bash
# Test database and server functionality
python test_mcp_server.py

# Validate MCP compliance
python validate_mcp_standards.py
```

## 🚀 Deployment

To run the MCP server as a public service on a Linux VPS:

### 1. Deploy to server

```bash
# Create service user
sudo useradd --system --shell /usr/sbin/nologin garmin-mcp

# Deploy code
sudo mkdir -p /opt/garmin-mcp
# (copy project files to /opt/garmin-mcp)
sudo chown -R garmin-mcp:garmin-mcp /opt/garmin-mcp

# Setup venv
sudo -u garmin-mcp python3 -m venv /opt/garmin-mcp/.venv
sudo -u garmin-mcp /opt/garmin-mcp/.venv/bin/pip install -r /opt/garmin-mcp/requirements.txt
```

### 2. Configure environment

Create `/opt/garmin-mcp/.env`:

```env
GARMIN_DB_PATH=/opt/garmin-mcp/garmin_activities.db
GARMIN_MCP_TRANSPORT=http
GARMIN_MCP_AUTH_TOKEN=<generate with: python3 -c "import secrets; print(secrets.token_urlsafe(32))">
GARMIN_MCP_HTTP_HOST=0.0.0.0
GARMIN_MCP_HTTP_PORT=8080
```

**Note:** Do not quote values in the `.env` file — systemd's `EnvironmentFile` does not handle quoted values.

### 3. Install systemd service

```bash
sudo cp /opt/garmin-mcp/deploy/garmin-mcp.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now garmin-mcp

# Verify
sudo systemctl status garmin-mcp
journalctl -u garmin-mcp -f
```

## 🔒 Security & Privacy

- **Local Storage** - All data stays on your machine
- **Secure Authentication** - MFA support with encrypted session storage
- **Read-Only API** - MCP server only reads data, never modifies
- **SQL Injection Protection** - Parameterized queries throughout
- **No External Dependencies** - No cloud services or third-party analytics

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Garth Library** - Excellent Garmin Connect API wrapper
- **Anthropic** - MCP protocol and Claude integration
- **Garmin** - For providing comprehensive activity data through their platform

## 🐛 Troubleshooting

### Common Issues

**"ModuleNotFoundError: No module named 'mcp'"**
- Invoke the interpreter inside the venv directly: `.venv/bin/python mcp_server.py`
- Reinstall dependencies with `.venv/bin/pip install -r requirements.txt`

**"Database not found"**
- Run the downloader first: `python garmin_connect_downloader.py`
- Check `GARMIN_DB_PATH` environment variable

**"Authentication failed"**
- Verify credentials in `.env` file
- Check if MFA is enabled on your Garmin account
- Delete session files in `.garmin/` folder to force re-authentication

**"No activities found"**
- Check `GARMIN_START_DATE` setting
- Verify your Garmin account has activities in the specified date range
- Try downloading with `download_all_activities()` for complete sync

---

**Ready to unlock insights from your fitness data? Get started with the Quick Start guide above! 🚀**