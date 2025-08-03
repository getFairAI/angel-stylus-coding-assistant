#!/bin/bash

# Angel Stylus Coding Assistant with MCP - Startup Script
echo "🤖 Angel Stylus Coding Assistant with MCP Support"
echo "=================================================="

# Check if Python is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 is not installed!"
    exit 1
fi

# Make the Python script executable
chmod +x run_mcp_assistant.py

# Run the Python startup script
python3 run_mcp_assistant.py 