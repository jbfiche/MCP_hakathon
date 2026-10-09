#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIRECTORY="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
REPORT_DIRECTORY="${CHROMATIN_REPORT_OUTPUT_DIR:-/home/jb/Desktop/Hackaton/data/reports}"

mkdir -p "${REPORT_DIRECTORY}"
cd "${PROJECT_DIRECTORY}"

exec npx @modelcontextprotocol/inspector \
    -e "CHROMATIN_REPORT_OUTPUT_DIR=${REPORT_DIRECTORY}" \
    -- uv run mcp run src/chromatin_report_mcp/server.py:mcp
