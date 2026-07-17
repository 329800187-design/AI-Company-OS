"""AI Company OS — Core 最小启动入口

只加载 Governance + Agent 发现/启用/执行 + Collaboration + MiniDelivery，
不加载旧 Boss/Workflow/Pipeline/Commander 等路由。

启动命令:
    uvicorn backend.core_app:app --reload --port 8000
"""
import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.version import VERSION

# ── Core 路由 ──────────────────────────────────────────
from backend.routers.governance_router import router as governance_router
from backend.routers.collaboration_router import router as collaboration_router
from backend.routers.minidelivery_router import router as minidelivery_router
from backend.routers.core_agent_router import router as core_agent_router

app = FastAPI(
    title="AI Company OS Core",
    description="最小 Core 启动入口 — Governance + Agent 管理 + Collaboration + MiniDelivery",
    version=VERSION,
)

# ── CORS ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── 注册路由 ───────────────────────────────────────────
app.include_router(governance_router)
app.include_router(collaboration_router)
app.include_router(minidelivery_router)
app.include_router(core_agent_router)


# ── 健康检查 ───────────────────────────────────────────
@app.get("/health", include_in_schema=False)
def health_check():
    """Core 健康检查端点"""
    import datetime
    return {"status": "ok", "mode": "core", "version": VERSION, "timestamp": datetime.datetime.now().isoformat()}


# Core deliberately has no startup hook.
#
# The full application initializes database-backed legacy services in
# backend.app. Core mode keeps startup side-effect free so it can be distributed
# as a small Governance + Agent + Collaboration runtime.
