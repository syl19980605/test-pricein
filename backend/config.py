import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
# 可指向任意 Anthropic 兼容端点（如 MiMo）。留空则用 Anthropic 官方默认地址。
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "").strip()
# Bobby agent 使用的模型名。换成 MiMo 时改成对应模型标识。
BOBBY_MODEL = os.getenv("BOBBY_MODEL", "claude-sonnet-4-6")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
BACKEND_HOST = os.getenv("BACKEND_HOST", "0.0.0.0")
BACKEND_PORT = int(os.getenv("BACKEND_PORT", "8000"))
DB_PATH = os.getenv("DB_PATH", str(BASE_DIR / "data" / "bobby.db"))
MONITOR_INTERVAL = int(os.getenv("MONITOR_INTERVAL_SECONDS", "300"))
CORS_ORIGINS = ["http://localhost:5173", "http://localhost:3000"]
