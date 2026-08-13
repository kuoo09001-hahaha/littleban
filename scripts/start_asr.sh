#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-caremate}"

if ! command -v conda >/dev/null 2>&1; then
  echo "找不到 Conda。请先安装 Miniconda 或 Anaconda。" >&2
  exit 1
fi

if ! conda run -n "$CONDA_ENV_NAME" python --version >/dev/null 2>&1; then
  echo "未找到 Conda 环境 $CONDA_ENV_NAME。请先运行：./scripts/setup_local.sh --with-asr" >&2
  exit 1
fi

cd "$PROJECT_ROOT/HDZB_ASR"
echo "ASR 会在首次启动时加载模型，可能需要较长时间。"
exec conda run --no-capture-output -n "$CONDA_ENV_NAME" python -m uvicorn main:app --host 127.0.0.1 --port 8015 --reload
