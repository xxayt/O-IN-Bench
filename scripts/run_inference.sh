#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# ===== 参数设置 =====
export DATA_ROOT="${DATA_ROOT:-./O-IN-Bench}"
export OUTPUT_DIR="${OUTPUT_DIR:-./outputs/model}"
export API_BASE="${API_BASE:-}"
export MODEL_NAME="${MODEL_NAME:-}"
export API_KEY="${API_KEY:-}"
export MAX_TOKENS="${MAX_TOKENS:-1024}"
export WORKERS="${WORKERS:-4}"
export MAX_SAMPLES="${MAX_SAMPLES:--1}"
export SKIP_SAMPLES="${SKIP_SAMPLES:-0}"
export OVERRIDE="${OVERRIDE:-0}"
export API_TIMEOUT="${API_TIMEOUT:-300}"

echo "Model=$MODEL_NAME Data=$DATA_ROOT Output=$OUTPUT_DIR Workers=$WORKERS Max=$MAX_SAMPLES Skip=$SKIP_SAMPLES Override=$OVERRIDE"
python -m eval.inference
