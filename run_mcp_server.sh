#!/bin/bash

# Garmin MCP Server Launcher Script
# This script activates the virtual environment and runs the MCP server

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Set the virtual environment path
VENV_PATH="$SCRIPT_DIR/.venv"

# Check if virtual environment exists
if [ ! -d "$VENV_PATH" ]; then
    echo "Virtual environment not found at $VENV_PATH" >&2
    exit 1
fi

# Check if MCP server exists
if [ ! -f "$SCRIPT_DIR/mcp_server.py" ]; then
    echo "MCP server not found at $SCRIPT_DIR/mcp_server.py" >&2
    exit 1
fi

# Set environment variables
export GARMIN_DB_PATH="${GARMIN_DB_PATH:-$SCRIPT_DIR/garmin_activities.db}"

# Run the MCP server using the virtual environment's Python
exec "$VENV_PATH/bin/python" "$SCRIPT_DIR/mcp_server.py" "$@"