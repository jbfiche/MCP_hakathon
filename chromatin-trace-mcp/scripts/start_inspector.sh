#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIRECTORY="$(cd -- "${SCRIPT_DIRECTORY}/.." && pwd)"
DATASET_CATALOG="${CHROMATIN_DATASETS_JSON:-${PROJECT_DIRECTORY}/datasets.local.json}"
OUTPUT_DIRECTORY="${CHROMATIN_TRACE_OUTPUT_DIR:-/home/jb/Desktop/Hackaton/data/mcp_outputs}"

if [[ ! -f "${DATASET_CATALOG}" ]]; then
    echo "Dataset catalog not found: ${DATASET_CATALOG}" >&2
    echo "Copy datasets.example.json to datasets.local.json and edit its paths." >&2
    exit 1
fi

mkdir -p "${OUTPUT_DIRECTORY}"
cd "${PROJECT_DIRECTORY}"

exec npx @modelcontextprotocol/inspector \
    -e "CHROMATIN_DATASETS_JSON=${DATASET_CATALOG}" \
    -e "CHROMATIN_TRACE_OUTPUT_DIR=${OUTPUT_DIRECTORY}" \
    -- uv run mcp run src/chromatin_trace_mcp/server.py:mcp
