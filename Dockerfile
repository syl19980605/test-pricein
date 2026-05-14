# ── 阶段 1：用 Node 构建前端 ──
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build
# 产物：/app/frontend/dist

# ── 阶段 2：Python 运行后端（同时托管前端 dist）──
FROM python:3.11-slim
WORKDIR /app

# 后端依赖
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

# 后端代码 + 上一阶段构建好的前端
COPY backend/ ./backend/
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

ENV PYTHONUNBUFFERED=1
# Render 会注入 $PORT；本地直接 docker run 时回退到 8000
CMD ["sh", "-c", "uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
