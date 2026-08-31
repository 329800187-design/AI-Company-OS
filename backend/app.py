"""AI Company OS - FastAPI 入口"""
import sys
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 中（解决 CWD 依赖问题）
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from backend.routers.task_router import router as task_router
from backend.routers.agent_router import router as agent_router
from backend.routers.workflow_router import router as workflow_router
from backend.routers.commander_router import router as commander_router
from backend.routers.config_router import router as config_router
from backend.routers.ai_registry_router import router as ai_registry_router
from backend.routers.template_router import router as template_router
from backend.routers.export_router import router as export_router
from backend.routers.usage_router import router as usage_router
from backend.routers.skill_router import router as skill_router
from backend.routers.memory_router import router as memory_router
from backend.routers.cto_router import router as cto_router
from backend.routers.image_router import router as image_router
from backend.routers.marketing_router import router as marketing_router
from backend.routers.user_router import router as user_router
from backend.routers.payment_router import router as payment_router
from backend.routers.metrics_router import router as metrics_router
from backend.routers.data_router import router as data_router
from backend.routers.cron_router import router as cron_router
from backend.routers.backup_router import router as backup_router
from backend.routers.search_router import router as search_router
from backend.routers.swarm_router import router as swarm_router
from backend.routers.audit_router import router as audit_router
from backend.routers.plugin_router import router as plugin_router
from backend.routers.auth_router import router as oauth_router
from backend.routers.apikey_router import router as apikey_router
from backend.routers.admin_router import router as admin_router
from backend.routers.agent_market_router import router as agent_market_router
from backend.routers.commander_manager_router import router as commander_manager_router
from backend.routers.plugin_config_router import router as plugin_config_router
from backend.routers.brain_router import router as brain_router
from backend.routers.pipeline_router import router as pipeline_router
from backend.routers.capabilities_router import router as capabilities_router
from backend.routers.browser_verification_router import router as browser_verification_router
from backend.routers.agent_console_router import router as agent_console_router
from backend.routers.boss_router import router as boss_router
from backend.routers.collaboration_router import router as collaboration_router
from backend.routers.minidelivery_router import router as minidelivery_router
from backend.routers.governance_router import router as governance_router
from backend.routers.feishu_router import router as feishu_router
from backend.database.database import init_db
from backend import config
from backend.task_queue.queue import BackgroundTaskManager
from backend.middleware.auth_middleware import AuthMiddleware, get_auth_config, set_auth_token, set_auth_enabled
from backend.middleware.error_handler import GlobalErrorMiddleware
from backend.middleware.audit import AuditMiddleware
from backend.middleware.tier_limits import TierLimitMiddleware
from backend.services.logger import log_api_request, log_info
from pydantic import BaseModel

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Company OS · 多智能体协作操作系统",
    description="多智能体协作系统 — 支持指挥官 / CEO / Codex / OpenClaw / QA 等多个智能体协同工作。",
    version="1.0.0",  # 统一版本号
    swagger_ui_parameters={
        "defaultModelsExpandDepth": -1,
        "docExpansion": "list",
        "filter": True,
        "tryItOutEnabled": True,
        "syntaxHighlight.theme": "monokai",
    },
    contact={
        "name": "AI Company OS",
        "url": "http://localhost:8000",
    },
)

# 全局错误处理（最外层，捕获所有异常）
app.add_middleware(GlobalErrorMiddleware)

# 审计日志
app.add_middleware(AuditMiddleware)

# Tier limits (agent execution caps per subscription)
app.add_middleware(TierLimitMiddleware)

# 静态文件 (CSS/JS)
FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend"
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")

# 新前端静态文件 (React)
NEW_FRONTEND_DIR = Path(__file__).resolve().parent.parent / "frontend-new" / "dist"
if NEW_FRONTEND_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(NEW_FRONTEND_DIR / "assets")), name="new-assets")

# API Key 认证中间件（开发模式默认不启用）
app.add_middleware(AuthMiddleware)

# CORS — 最后注册 = 最外层，保证错误响应也有 CORS 头
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

app.include_router(task_router)
app.include_router(agent_router)
app.include_router(workflow_router)
app.include_router(commander_router)
app.include_router(config_router)
app.include_router(ai_registry_router)
app.include_router(template_router)
app.include_router(export_router)
app.include_router(usage_router)
app.include_router(skill_router)
app.include_router(memory_router)
app.include_router(cto_router)
app.include_router(image_router)
app.include_router(marketing_router)
app.include_router(user_router)
app.include_router(payment_router)
app.include_router(metrics_router)
app.include_router(data_router)
app.include_router(cron_router)
app.include_router(backup_router)
app.include_router(search_router)
app.include_router(swarm_router)
app.include_router(audit_router)
app.include_router(plugin_router)
app.include_router(oauth_router)
app.include_router(apikey_router)
app.include_router(admin_router)
app.include_router(agent_market_router)
app.include_router(commander_manager_router)
app.include_router(plugin_config_router)
app.include_router(brain_router)
app.include_router(pipeline_router)
app.include_router(capabilities_router)
app.include_router(browser_verification_router)
app.include_router(boss_router)
app.include_router(agent_console_router)
app.include_router(collaboration_router)
app.include_router(minidelivery_router)
app.include_router(governance_router)
app.include_router(feishu_router)

# 多租户认证中间件（轻量 — 解析 Authorization Header 中的用户 token）
@app.middleware("http")
async def tenant_auth_middleware(request, call_next):
    from backend.auth.user_system import get_user_manager
    from starlette.requests import Request as _R
    token = request.headers.get("Authorization", "").replace("Bearer ", "")
    request.state.user = None
    request.state.tenant_id = "default"
    if token:
        user = get_user_manager().validate_token(token)
        if user:
            request.state.user = user
            request.state.tenant_id = user.get("tenant_id", "default")
    return await call_next(request)

# 初始化后台任务管理器（在模块级别，TestClient 也能访问）
manager = BackgroundTaskManager(max_workers=4)
app.state.manager = manager

# 日志记录中间件 — 记录所有 API 请求（加版本头）
@app.middleware("http")
async def log_and_version(request, call_next):
    import time as _time
    start = _time.time()
    response = await call_next(request)
    duration = int((_time.time() - start) * 1000)
    response.headers["X-API-Version"] = "1.5.0"
    response.headers["X-Response-Time-Ms"] = str(duration)
    from backend.services.logger import log_api_request
    log_api_request(method=request.method, path=request.url.path, status=response.status_code, duration_ms=duration)
    return response

# 认证配置端点（在中间件外层，免鉴权）
@app.get("/auth/info", include_in_schema=False)
def auth_info():
    """获取当前认证状态（不返回完整 Token）"""
    cfg = get_auth_config()
    return {
        "enabled": cfg["enabled"],
        "token_preview": cfg["token"][:8] + "..." if cfg["token"] else "",
        # Never return full token for security
    }


class AuthConfigRequest(BaseModel):
    """认证配置请求"""
    enabled: bool = False
    token: str = ""


@app.get("/health", include_in_schema=False)
def health_check():
    """健康检查端点（免鉴权）"""
    import datetime
    return {"status": "ok", "version": "1.5.0", "timestamp": datetime.datetime.now().isoformat()}


@app.post("/auth/config", include_in_schema=False)
def auth_config(request: AuthConfigRequest):
    """更新认证配置（运行时生效，不持久化到 .env）"""
    set_auth_enabled(request.enabled)
    if request.token:
        set_auth_token(request.token)
    return {"status": "ok", "enabled": request.enabled}

# 启动时初始化数据库
@app.on_event("startup")
def startup():
    from backend.runtime_paths import bootstrap_runtime_storage
    bootstrap_runtime_storage()
    init_db()
    log_info("system", "AI Company OS 启动完成", version="1.0.0", provider=config.AI_PROVIDER)

    # 清理超时的 running 状态模块（非阻塞，快速完成）
    try:
        from backend.services.boss_command_center import get_boss_command_center
        result = get_boss_command_center().cleanup_stale_running_missions(timeout_minutes=30)
        if result["cleaned_modules"] > 0:
            log_info("system", f"启动时清理了 {result['cleaned_modules']} 个超时 running 模块",
                     affected_missions=result["affected_missions"])
    except Exception as e:
        logger.error(f"Startup stale cleanup failed: {e}")


# WebSocket 端点 — 任务进度实时推送（支持 token 认证）
@app.websocket("/ws/task/{task_id}")
async def task_ws(websocket: WebSocket, task_id: str):
    """WebSocket 实时任务进度推送

    认证方式：查询参数 ?token=xxx（浏览器 WebSocket 不支持自定义 Header）
    连接后自动收到当前任务状态，之后每步执行都会推送进度。
    """
    # 检查认证（从查询参数读取 token，与 HTTP 中间件保持一致）
    from backend.middleware.auth_middleware import get_auth_config
    auth_cfg = get_auth_config()
    if auth_cfg["enabled"] and auth_cfg["token"]:
        query_token = websocket.query_params.get("token", "")
        if query_token != auth_cfg["token"]:
            await websocket.close(code=4001, reason="认证失败: token 无效")
            return

    await websocket.accept()
    try:
        await app.state.manager.subscribe(task_id, websocket)
        # 保持连接，等待客户端断开
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await app.state.manager.unsubscribe(task_id, websocket)
    except Exception:
        try:
            await app.state.manager.unsubscribe(task_id, websocket)
        except Exception:
            pass

# 前端 UI 页面
FRONTEND_HTML = Path(__file__).parent.parent / "frontend" / "index.html"
if FRONTEND_HTML.exists():
    _UI_HTML = FRONTEND_HTML.read_text(encoding="utf-8")

    @app.get("/ui", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/ui/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    def ui_page(full_path: str = ""):
        """返回前端页面"""
        return HTMLResponse(content=_UI_HTML)

# 新前端 UI 页面 (React 科技感版本)
NEW_FRONTEND_HTML = Path(__file__).parent.parent / "frontend-new" / "dist" / "index.html"

if NEW_FRONTEND_HTML.exists():
    @app.get("/app", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/app/", response_class=HTMLResponse, include_in_schema=False)
    @app.get("/app/{full_path:path}", response_class=HTMLResponse, include_in_schema=False)
    def new_ui_page(full_path: str = ""):
        """返回新前端页面（React 科技感版本）— 每次请求从磁盘读取，避免 stale build"""
        return HTMLResponse(content=NEW_FRONTEND_HTML.read_text(encoding="utf-8"))


@app.get("/api/versions", include_in_schema=False)
def api_versions():
    return {"versions": [
        {"v":"0.1.0","date":"","milestone":"CEO+QA+内存Task MVP"},
        {"v":"0.4.0","date":"","milestone":"11 Agent完整"},
        {"v":"0.5.0","date":"","milestone":"DAG+多租户+OpenClaw v2"},
        {"v":"0.6.0","date":"","milestone":"Image路由+Cache+Embedding+前端组件化"},
        {"v":"0.7.0","date":"","milestone":"Agent标准化+Stripe+监控面板"},
        {"v":"0.8.0","date":"","milestone":"Data Agent+Cron+Agent Bus+Pydantic"},
        {"v":"0.9.0","date":"","milestone":"限流+备份恢复+全文搜索+Swarm"},
        {"v":"1.5.0","date":"","milestone":"全局异常+RBAC+拆解缓存+审计+生产部署"},
    ]}


@app.get("/")
def root():
    return {
        "name": "AI Company OS",
        "version": "1.5.0",
        "status": "running · 运行中",
        "endpoints": {
            "ui": "/ui - 经典界面",
            "app": "/app - 新版科技感界面（推荐）",
            "commander": "/commander - 指挥官主脑（自主规划执行）",
            "skills": "/skills - 技能系统（插件化能力+学习）",
            "cto": "/cto - 技术架构审查（代码审查/技术选型/架构评审）",
            "image": "/image - AI 图片生成（DALL-E 3）",
            "marketing": "/marketing - 营销内容生成（文案/SEO/社媒/邮件/品牌/活动）",
            "memory": "/memory - 记忆系统（持久化+自动检索）",
            "agents": "/agents - 智能体调用 (CEO/Codex/OpenClaw/System/QA/CTO/Image/Marketing/Video)",
            "workflows": "/workflows - 多智能体工作流",
            "config": "/config - 配置管理（API Key / Provider）",
            "ai": "/ai - AI 资源注册中心（扫描/路由/调用）",
            "ui": "/ui - 前端可视化操作台",
            "docs": "/docs - Swagger 中文文档",
        },
    }


@app.get("/system/info", include_in_schema=False)
def system_info():
    """系统综合信息 — Agent数/技能数/Provider/版本等"""
    try:
        from core.skills.skill_manager import get_skill_manager
        skills = get_skill_manager().list_all()
        skill_count = len(skills)
    except Exception:
        skill_count = -1

    try:
        from backend.ai_registry.registry import get_registry
        svcs = get_registry().list_all()
        online = sum(1 for s in svcs if s.get("status") in ("online", "running"))
        ai_services = {"total": len(svcs), "online": online}
    except Exception:
        ai_services = {"total": -1, "online": 0}

    try:
        from backend.services.usage_stats import get_all_time_stats
        usage = get_all_time_stats()
    except Exception:
        usage = {}

    return {
        "name": "AI Company OS",
        "version": "1.5.0",
        "provider": config.AI_PROVIDER,
        "agents": {
            "total": 10,
            "internal": ["commander", "ceo", "codex", "openclaw", "qa", "system", "cto", "data"],
            "creative": ["image", "marketing", "video"],
        },
        "skills": {"count": skill_count},
        "ai_services": ai_services,
        "usage": {
            "total_calls": usage.get("total_calls", 0),
            "total_tokens": usage.get("total_tokens", 0),
            "estimated_cost_yuan": usage.get("estimated_cost_yuan", 0.0),
        },
        "process": {
            "python": __import__('sys').version.split()[0],
            "platform": __import__('sys').platform,
        },
    }
