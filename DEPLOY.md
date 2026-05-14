# 部署到 Render（单服务，一个 URL，邮件分享即点即用）

整个应用打包成**一个服务**：FastAPI 同时托管打包好的前端静态文件 + `/api` 路由。
前后端同源，对方点开链接直接能用。

## 一、前置：把代码推到 Git 仓库

Render 从 Git 仓库部署。当前目录还不是 git 仓库，先初始化并推到 GitHub：

```bash
cd /Users/bytedance/Documents/Claude/rockflow_test
git init
git add .                      # .env 已被 .gitignore 排除，密钥不会进仓库
git commit -m "Bobby AI Agent demo"
# 在 GitHub 新建一个空仓库，然后：
git remote add origin git@github.com:<你的用户名>/<仓库名>.git
git push -u origin main
```

> ⚠️ 确认 `git status` 里**没有 `.env`** —— 它在 `.gitignore` 里，密钥不该进仓库。

## 二、在 Render 上部署

1. 注册/登录 [render.com](https://render.com)
2. 点 **New +** → **Blueprint**
3. 连接你的 GitHub 仓库 → Render 会自动读取根目录的 `render.yaml`
4. 部署前会让你填 `render.yaml` 里标了 `sync: false` 的密钥：
   - **`ANTHROPIC_API_KEY`** → 填你的 MiMo key：`tp-ck1vgusy5ptc48zv66jagjew2jk554jl7rv1ttwri6yxbih3`
   - **`NEWSAPI_KEY`** → 可留空
5. 点 **Apply** → Render 用 `Dockerfile` 构建（Node 构前端 → Python 跑后端），约 3-5 分钟
6. 构建完成后拿到形如 `https://bobby-ai-agent.onrender.com` 的 URL —— 这就是邮件里发的链接

## 三、几个要知道的点

- **档位**：`render.yaml` 里是 `plan: starter`（$7/月），常驻不休眠，点开即用。
- **数据是临时的**：SQLite 存在容器里，每次**重新部署**会重置（监控、持仓、对话历史清空）。
  对 demo 没影响 —— 演示期间别重新部署即可。若要持久化，给服务挂一个 Render Disk
  并设环境变量 `DB_PATH=/data/bobby.db`。
- **Bobby 回复需 30-60 秒**：它是真实 AI agent，要调 MiMo 推理 + 多个工具。
  **建议在邮件里写一句**："Bobby 是真实 AI agent，每次分析约需 30-60 秒，请耐心等待"。
- **额度**：别人用这个链接 = 消耗你的 MiMo key 额度。
- **更新**：改完代码 `git push`，Render 会自动重新构建部署。

## 四、本地验证（部署前先跑一遍单服务模式）

```bash
# 1. 构建前端
cd frontend && npm run build && cd ..
# 2. 起后端（会自动托管 frontend/dist）
python3 -m uvicorn backend.main:app --port 8000
# 3. 浏览器打开 http://localhost:8000 —— 前后端同源，整个应用都在这一个端口
```
