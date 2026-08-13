#!/usr/bin/env bash
set -euo pipefail

# Create a project-specific Conda environment and install only the text Agent
# by default. Pass --with-asr to also install the heavier speech stack.
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONDA_ENV_NAME="${CONDA_ENV_NAME:-caremate}"
PYTHON_VERSION="${PYTHON_VERSION:-3.11}"
INSTALL_ASR=false

if [[ "${1:-}" == "--with-asr" ]]; then
  INSTALL_ASR=true
fi

if ! command -v conda >/dev/null 2>&1; then
  echo "找不到 Conda.请先安装 Miniconda 或 Anaconda,并重新打开终端。" >&2
  exit 1
fi

if ! conda run -n "$CONDA_ENV_NAME" python --version >/dev/null 2>&1; then
  echo "正在创建 Conda 环境：$CONDA_ENV_NAME(Python $PYTHON_VERSION)"
  conda create --yes --name "$CONDA_ENV_NAME" "python=$PYTHON_VERSION"
fi

conda run --no-capture-output -n "$CONDA_ENV_NAME" python -m pip install --upgrade pip
conda run --no-capture-output -n "$CONDA_ENV_NAME" python -m pip install -r "$PROJECT_ROOT/HDZB_agent/requirements.txt"

if [[ "$INSTALL_ASR" == true ]]; then
  # FunASR's audio loader uses TorchCodec on macOS. Installing FFmpeg inside
  # the same Conda environment provides the libav* dynamic libraries it needs.
  conda install --yes --name "$CONDA_ENV_NAME" --channel conda-forge ffmpeg
  conda run --no-capture-output -n "$CONDA_ENV_NAME" python -m pip install -r "$PROJECT_ROOT/HDZB_ASR/requirements.txt"
fi

if [[ ! -f "$PROJECT_ROOT/HDZB_agent/.env" ]]; then
  cp "$PROJECT_ROOT/.env.example" "$PROJECT_ROOT/HDZB_agent/.env"
  echo "已创建 HDZB_agent/.env，请填入 ARK_API_KEY 和 AMAP_API_KEY 后再启动服务。"
else
  echo "保留已有 HDZB_agent/.env，未覆盖其中的本地配置。"
fi

echo "环境已准备好。启动文本 Agent：./scripts/start_agent.sh"
echo "如需手动进入环境：conda activate $CONDA_ENV_NAME"
