#!/usr/bin/env bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR/.."

# ===== 参数设置 =====
export DATA_ROOT="${DATA_ROOT:-./O-IN-Bench}"
export PREDICTIONS="${PREDICTIONS:-./outputs/model/predictions.jsonl}"
export SCORE_DIR="${SCORE_DIR:-./outputs/model/scores}"
export JUDGE_API_BASE="${JUDGE_API_BASE:-}"
export JUDGE_API_KEY="${JUDGE_API_KEY:-}"
export JUDGE_MODEL="${JUDGE_MODEL:-gpt-6-luna}"
export WORKERS="${WORKERS:-4}"
export OVERRIDE="${OVERRIDE:-0}"
export API_TIMEOUT="${API_TIMEOUT:-300}"

echo "Judge=$JUDGE_MODEL Data=$DATA_ROOT Predictions=$PREDICTIONS Output=$SCORE_DIR Workers=$WORKERS Override=$OVERRIDE"
python -m eval.score
