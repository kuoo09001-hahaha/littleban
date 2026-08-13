#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-caremate}"
ENV_FILE="$PROJECT_ROOT/HDZB_agent/.env"

if ! command -v conda >/dev/null 2>&1; then
  echo "找不到 Conda。请先安装 Miniconda 或 Anaconda。" >&2
  exit 1
fi

if ! conda run -n "$CONDA_ENV_NAME" python --version >/dev/null 2>&1; then
  echo "未找到 Conda 环境 $CONDA_ENV_NAME。请先运行:./scripts/setup_local.sh" >&2
  exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
  echo "未找到 HDZB_agent/.env。请先运行：./scripts/setup_local.sh" >&2
  exit 1
fi

if grep -q '^ARK_API_KEY=replace-with-your-ark-api-key$' "$ENV_FILE"; then
  echo "请先在 HDZB_agent/.env 中填写 ARK_API_KEY。" >&2
  exit 1
fi

cd "$PROJECT_ROOT/HDZB_agent"
echo "文本 Agent 已启动后，请打开：http://127.0.0.1:8017/docs"
exec conda run --no-capture-output -n "$CONDA_ENV_NAME" python -m uvicorn main_agent:app --host 127.0.0.1 --port 8017 --reload
