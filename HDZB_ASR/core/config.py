import os
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - keeps config usable before dependencies are installed
    load_dotenv = None


if load_dotenv:
    project_root = Path(__file__).resolve().parents[2]
    load_dotenv(project_root / ".env")
    load_dotenv(project_root / "HDZB_ASR" / ".env")


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


def _normalize_base_url(url: str) -> str:
    return url.rstrip("/")


# ---------------- 全局配置 ----------------
HOST = os.getenv("ASR_SERVER_HOST", "0.0.0.0")   # IP地址
PORT = _get_int("ASR_SERVER_PORT", 8015)        # 统一端口
LOG_LEVEL = os.getenv("LOG_LEVEL", "info")

# 下游服务地址
COMPANION_SERVICE_URL = _normalize_base_url(os.getenv("COMPANION_SERVICE_URL", "http://localhost:8016"))
AGENT_SERVICE_URL = _normalize_base_url(os.getenv("AGENT_SERVICE_URL", "http://localhost:8017"))

COMPANION_CHAT_URL = f"{COMPANION_SERVICE_URL}/chat"
COMPANION_STREAM_URL = f"{COMPANION_SERVICE_URL}/chat/stream"
COMPANION_HEALTH_URL = f"{COMPANION_SERVICE_URL}/health"
AGENT_CHAT_URL = f"{AGENT_SERVICE_URL}/agent/chat"
AGENT_AUDIO_CHAT_URL = f"{AGENT_SERVICE_URL}/agent/audio-chat"
AGENT_HEALTH_URL = f"{AGENT_SERVICE_URL}/agent/health"

# 本地文件保存路径
SAVE_FILE_DIR = os.getenv("SAVE_FILE_DIR", "./data/uploads")

# 转码默认参数
DEFAULT_AC = _get_int("DEFAULT_AC", 1)         # 单声道
DEFAULT_AR = _get_int("DEFAULT_AR", 16000)     # 采样率 16kHz
DEFAULT_BITRATE = os.getenv("DEFAULT_BITRATE", "32k")  # 比特率 32kbps
