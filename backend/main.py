import logging
from contextlib import asynccontextmanager
from pathlib import Path

from dotenv import load_dotenv

# override=True：让 .env 文件优先于 shell 环境变量。
# 本地开发时 .env 提供配置；生产环境（Render）没有 .env 文件，
# load_dotenv 会静默跳过，直接用平台注入的环境变量。
load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from backend.config import BASE_DIR, CORS_ORIGINS
from backend.models.database import init_db, close_db
from backend.routers import assets, chat, signals, positions, alerts, monitors
from backend.tasks.monitor import start_scheduler, stop_scheduler

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    start_scheduler()
    yield
    stop_scheduler()
    await close_db()


app = FastAPI(title="Bobby AI Agent", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(assets.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(signals.router, prefix="/api/v1")
app.include_router(positions.router, prefix="/api/v1")
app.include_router(alerts.router, prefix="/api/v1")
app.include_router(monitors.router, prefix="/api/v1")


@app.get("/api/health")
async def health():
    return {"status": "ok"}


# ── 单服务部署：FastAPI 同时托管打包好的前端 ──
# 生产环境前端会被构建到 frontend/dist/，由本服务直接托管，
# 前后端同源、一个 URL、无需 CORS 代理。本地开发时 dist 不存在则跳过（用 Vite dev server）。
# 注意：必须放在所有 /api 路由之后 —— mount("/") 很贪婪，会兜住其余所有路径。
_FRONTEND_DIST = BASE_DIR / "frontend" / "dist"
if _FRONTEND_DIST.is_dir():
    app.mount("/", StaticFiles(directory=str(_FRONTEND_DIST), html=True), name="frontend")
    logging.info(f"Serving frontend from {_FRONTEND_DIST}")
else:
    logging.info("frontend/dist 不存在 —— 仅 API 模式（本地开发用 Vite dev server）")
