#!/bin/bash
# Copy new data from the Pi to this Mac, then merge any finished days.
# Usage (from the project root): ./sync.sh
# Needs a .env file (not committed) containing: PI=username@hostname.local

set -e
cd "$(dirname "$0")"
source .env

rsync -av --exclude '*.tmp' "$PI:~/Bikeshare-Toronto-MCP/data/" data/

cd collector
uv run python -c "from collector import merge_finished_days; print('Merged:', merge_finished_days())"
