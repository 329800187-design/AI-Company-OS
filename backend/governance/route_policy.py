"""Route Governance Inventory — 路由分级策略注册表"""
from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Set


class RoutePolicy(BaseModel):
    """路由策略定义"""
    path: str
    methods: List[str] = Field(default_factory=lambda: ["GET"])
    category: str  # controlled | protected | safe_read | deprecated | internal | high_risk | unknown
    requires_governance: bool = False
    has_guard: bool = False
    owner: str = ""
    reason: str = ""
    replacement: Optional[str] = None


# ── 路由策略注册表 ──────────────────────────────────────────

_POLICIES: List[RoutePolicy] = [
    # ── controlled: Governance 受控入口 ────────────────────
    RoutePolicy(path="/governance/classify", methods=["POST"], category="controlled",
                owner="governance", reason="Governance 分类入口，纯计算无副作用"),
    RoutePolicy(path="/governance/plan", methods=["POST"], category="controlled",
                owner="governance", reason="Governance 计划构建入口"),
    RoutePolicy(path="/governance/run", methods=["POST"], category="controlled",
                requires_governance=True, owner="governance",
                reason="Governance 主执行入口，内置分类+计划+执行+记录，支持单能力和多智能体协同"),
    RoutePolicy(path="/governance/runs/{run_id}", methods=["GET"], category="safe_read",
                owner="governance", reason="查询运行记录"),
    RoutePolicy(path="/governance/runs/{run_id}/events", methods=["GET"], category="safe_read",
                owner="governance", reason="查询运行事件"),

    # ── controlled: Collaboration 协同计划入口 ───────────────
    RoutePolicy(path="/collaboration/plan", methods=["POST"], category="controlled",
                owner="collaboration", reason="协作计划构建，纯计算无副作用"),
    RoutePolicy(path="/collaboration/run", methods=["POST"], category="controlled",
                requires_governance=True, owner="collaboration",
                reason="协作计划构建+执行"),

    # ── controlled: MiniDelivery 受控入口 ──────────────────
    RoutePolicy(path="/minidelivery/copy-pack", methods=["POST"], category="controlled",
                requires_governance=True, owner="minidelivery",
                reason="通用文案包生成，经过验收的受控闭环"),
    RoutePolicy(path="/minidelivery/xhs-copy-pack", methods=["POST"], category="controlled",
                requires_governance=True, owner="minidelivery",
                reason="小红书文案包生成，旧接口兼容"),
    RoutePolicy(path="/minidelivery/tasks/{task_id}", methods=["GET"], category="safe_read",
                owner="minidelivery", reason="查询任务结果"),
    RoutePolicy(path="/minidelivery/tasks/{task_id}/artifact", methods=["GET"], category="safe_read",
                owner="minidelivery", reason="读取产物内容"),

    # ── protected: 已接入 Governance Guard ─────────────────
    RoutePolicy(path="/commander/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="commander",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/commander/run-async", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="commander",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),

    # ── safe_read: 只读/查询接口 ──────────────────────────
    RoutePolicy(path="/health", methods=["GET"], category="safe_read",
                owner="app", reason="健康检查"),
    RoutePolicy(path="/docs", methods=["GET"], category="safe_read",
                owner="app", reason="Swagger 文档"),
    RoutePolicy(path="/openapi.json", methods=["GET"], category="safe_read",
                owner="app", reason="OpenAPI Schema"),
    RoutePolicy(path="/commander/tasks/{task_id}", methods=["GET"], category="safe_read",
                owner="commander", reason="查询后台任务状态"),
    RoutePolicy(path="/commander/tasks", methods=["GET"], category="safe_read",
                owner="commander", reason="列出所有后台任务"),
    RoutePolicy(path="/commander/sessions", methods=["GET"], category="safe_read",
                owner="commander", reason="查看所有执行记录"),
    RoutePolicy(path="/commander/sessions/{session_id}", methods=["GET"], category="safe_read",
                owner="commander", reason="查看执行详情"),
    RoutePolicy(path="/workflows/dag/list", methods=["GET"], category="safe_read",
                owner="workflow", reason="列出 DAG 工作流"),
    RoutePolicy(path="/workflows/dag/{name}", methods=["GET"], category="safe_read",
                owner="workflow", reason="查看 DAG 工作流详情"),
    RoutePolicy(path="/boss/templates", methods=["GET"], category="safe_read",
                owner="boss", reason="模板列表"),
    RoutePolicy(path="/boss/missions", methods=["GET"], category="safe_read",
                owner="boss", reason="Mission 列表"),
    RoutePolicy(path="/boss/missions/{mission_id}", methods=["GET"], category="safe_read",
                owner="boss", reason="Mission 详情"),
    RoutePolicy(path="/boss/missions/{mission_id}/events", methods=["GET"], category="safe_read",
                owner="boss", reason="Mission 事件日志"),
    RoutePolicy(path="/boss/modules/definitions", methods=["GET"], category="safe_read",
                owner="boss", reason="模块定义"),
    RoutePolicy(path="/pipeline/health", methods=["GET"], category="safe_read",
                owner="pipeline", reason="流水线健康检查"),
    RoutePolicy(path="/templates/list", methods=["GET"], category="safe_read",
                owner="template", reason="模板列表"),
    RoutePolicy(path="/templates/{template_id}", methods=["GET"], category="safe_read",
                owner="template", reason="模板详情"),
    RoutePolicy(path="/ai/list", methods=["GET"], category="safe_read",
                owner="ai_registry", reason="列出 AI 资源"),
    RoutePolicy(path="/ai/capabilities", methods=["GET"], category="safe_read",
                owner="ai_registry", reason="获取可用能力"),
    RoutePolicy(path="/ai/service/{service_id}", methods=["GET"], category="safe_read",
                owner="ai_registry", reason="获取单个 AI 服务详情"),
    RoutePolicy(path="/swarm/agents", methods=["GET"], category="safe_read",
                owner="swarm", reason="Swarm Agent 列表"),
    RoutePolicy(path="/usage/stats", methods=["GET"], category="safe_read",
                owner="usage", reason="AI 使用量统计"),
    RoutePolicy(path="/usage/total", methods=["GET"], category="safe_read",
                owner="usage", reason="总使用量"),
    RoutePolicy(path="/usage/recent", methods=["GET"], category="safe_read",
                owner="usage", reason="最近调用记录"),
    RoutePolicy(path="/export/session/{session_id}", methods=["GET"], category="safe_read",
                owner="export", reason="导出执行结果"),
    RoutePolicy(path="/system/audit", methods=["GET"], category="safe_read",
                owner="audit", reason="审计日志查询"),
    RoutePolicy(path="/system/metrics", methods=["GET"], category="safe_read",
                owner="metrics", reason="监控面板数据"),
    RoutePolicy(path="/system/health", methods=["GET"], category="safe_read",
                owner="metrics", reason="Agent 详细健康"),
    RoutePolicy(path="/system/doctor", methods=["GET"], category="safe_read",
                owner="metrics", reason="Runtime 自检"),
    RoutePolicy(path="/system/capabilities", methods=["GET"], category="safe_read",
                owner="metrics", reason="能力就绪矩阵"),
    RoutePolicy(path="/capabilities", methods=["GET"], category="safe_read",
                owner="capabilities", reason="获取本地能力"),
    RoutePolicy(path="/capabilities/summary", methods=["GET"], category="safe_read",
                owner="capabilities", reason="获取能力摘要"),
    RoutePolicy(path="/brain/", methods=["GET"], category="safe_read",
                owner="brain", reason="获取系统状态"),
    RoutePolicy(path="/brain/list", methods=["GET"], category="safe_read",
                owner="brain", reason="列出所有主脑"),
    RoutePolicy(path="/brain/current", methods=["GET"], category="safe_read",
                owner="brain", reason="获取当前主脑"),
    RoutePolicy(path="/brain/health", methods=["GET"], category="safe_read",
                owner="brain", reason="主脑健康检查"),
    RoutePolicy(path="/brain/auto-select", methods=["GET"], category="safe_read",
                owner="brain", reason="自动选择最佳主脑"),
    RoutePolicy(path="/brain/capabilities", methods=["GET"], category="safe_read",
                owner="brain", reason="扫描本机能力"),
    RoutePolicy(path="/brain/capabilities/ai-services", methods=["GET"], category="safe_read",
                owner="brain", reason="可用 AI 服务"),
    RoutePolicy(path="/brain/capabilities/best", methods=["GET"], category="safe_read",
                owner="brain", reason="最佳 AI 服务"),
    RoutePolicy(path="/memory/search", methods=["GET"], category="safe_read",
                owner="memory", reason="搜索记忆"),
    RoutePolicy(path="/memory/recent", methods=["GET"], category="safe_read",
                owner="memory", reason="最近记忆"),
    RoutePolicy(path="/memory/context", methods=["GET"], category="safe_read",
                owner="memory", reason="获取记忆上下文"),
    RoutePolicy(path="/skills/list", methods=["GET"], category="safe_read",
                owner="skills", reason="列出所有技能"),
    RoutePolicy(path="/skills/match", methods=["GET"], category="safe_read",
                owner="skills", reason="匹配相关技能"),
    RoutePolicy(path="/skills/context", methods=["GET"], category="safe_read",
                owner="skills", reason="获取技能上下文"),
    RoutePolicy(path="/tasks/", methods=["GET"], category="safe_read",
                owner="tasks", reason="获取所有任务"),
    RoutePolicy(path="/tasks/{task_id}", methods=["GET"], category="safe_read",
                owner="tasks", reason="查询单个任务"),
    RoutePolicy(path="/cron/list", methods=["GET"], category="safe_read",
                owner="cron", reason="列出所有定时任务"),
    RoutePolicy(path="/cron/logs", methods=["GET"], category="safe_read",
                owner="cron", reason="执行日志"),
    RoutePolicy(path="/search", methods=["GET"], category="safe_read",
                owner="search", reason="全文搜索"),
    RoutePolicy(path="/marketplace/agents", methods=["GET"], category="safe_read",
                owner="marketplace", reason="列出可用 Agent"),
    RoutePolicy(path="/marketplace/agents/{agent_id}", methods=["GET"], category="safe_read",
                owner="marketplace", reason="获取 Agent 详情"),
    RoutePolicy(path="/marketplace/installed", methods=["GET"], category="safe_read",
                owner="marketplace", reason="已安装 Agent"),
    RoutePolicy(path="/marketplace/categories", methods=["GET"], category="safe_read",
                owner="marketplace", reason="Agent 分类"),
    RoutePolicy(path="/agent-console/agents", methods=["GET"], category="safe_read",
                owner="agent_console", reason="获取所有 Agent"),
    RoutePolicy(path="/agent-console/route/{task_type}", methods=["GET"], category="safe_read",
                owner="agent_console", reason="查看路由决策"),
    RoutePolicy(path="/commanders/", methods=["GET"], category="safe_read",
                owner="commander_manager", reason="列出所有指挥官"),
    RoutePolicy(path="/commanders/current", methods=["GET"], category="safe_read",
                owner="commander_manager", reason="获取当前指挥官"),
    RoutePolicy(path="/commanders/health", methods=["GET"], category="safe_read",
                owner="commander_manager", reason="指挥官健康检查"),
    RoutePolicy(path="/config/providers", methods=["GET"], category="safe_read",
                owner="config", reason="获取 Provider 状态"),
    RoutePolicy(path="/config/status", methods=["GET"], category="safe_read",
                owner="config", reason="获取配置状态"),
    RoutePolicy(path="/admin/users", methods=["GET"], category="safe_read",
                owner="admin", reason="列出所有用户"),
    RoutePolicy(path="/admin/stats", methods=["GET"], category="safe_read",
                owner="admin", reason="管理后台统计"),
    RoutePolicy(path="/user/me", methods=["GET"], category="safe_read",
                owner="user", reason="获取当前用户信息"),
    RoutePolicy(path="/user/limits", methods=["GET"], category="safe_read",
                owner="user", reason="查询套餐限制"),
    RoutePolicy(path="/user/usage", methods=["GET"], category="safe_read",
                owner="user", reason="查询用量统计"),
    RoutePolicy(path="/user/tiers", methods=["GET"], category="safe_read",
                owner="user", reason="获取套餐信息"),
    RoutePolicy(path="/user/api-keys", methods=["GET"], category="safe_read",
                owner="apikey", reason="列出 API Keys"),
    RoutePolicy(path="/payment/history", methods=["GET"], category="safe_read",
                owner="payment", reason="支付历史"),
    RoutePolicy(path="/payment/prices", methods=["GET"], category="safe_read",
                owner="payment", reason="价格列表"),
    RoutePolicy(path="/payment/status", methods=["GET"], category="safe_read",
                owner="payment", reason="支付系统状态"),
    RoutePolicy(path="/plugins", methods=["GET"], category="safe_read",
                owner="plugin", reason="列出外部插件"),
    RoutePolicy(path="/plugins/{plugin_id}", methods=["GET"], category="safe_read",
                owner="plugin_config", reason="获取插件详情"),
    RoutePolicy(path="/plugins/templates/list", methods=["GET"], category="safe_read",
                owner="plugin_config", reason="插件代码模板列表"),
    RoutePolicy(path="/system/backups", methods=["GET"], category="safe_read",
                owner="backup", reason="列出备份文件"),
    RoutePolicy(path="/integrations/feishu/health", methods=["GET"], category="safe_read",
                owner="feishu", reason="飞书机器人状态"),

    # ── internal: AI 对话/内部工具 ─────────────────────────
    RoutePolicy(path="/commander/chat/send", methods=["POST"], category="internal",
                owner="commander", reason="AI 纯对话，未纳入 Governance 能力目录，不经过任务编排"),
    RoutePolicy(path="/ai/scan", methods=["GET"], category="internal",
                owner="ai_registry", reason="重新扫描 AI 资源，内部操作"),
    RoutePolicy(path="/ai/route", methods=["POST"], category="internal",
                owner="ai_registry", reason="AI 智能路由，内部调度"),
    RoutePolicy(path="/agent-console/refresh", methods=["POST"], category="internal",
                owner="agent_console", reason="重新扫描 Agent，内部操作"),
    RoutePolicy(path="/capabilities/refresh", methods=["POST"], category="internal",
                owner="capabilities", reason="刷新能力扫描，内部操作"),

    # ── deprecated: 旧执行入口，已阻断返回 410 ───────────────
    RoutePolicy(path="/workflows/ceo-create-task", methods=["POST"], category="deprecated",
                requires_governance=True, has_guard=True, owner="workflow",
                reason="已阻断，返回 410，不再允许绕过 Governance 执行旧 CEO 拆解入口",
                replacement="/governance/run"),
    RoutePolicy(path="/workflows/ceo-codex-task", methods=["POST"], category="deprecated",
                requires_governance=True, has_guard=True, owner="workflow",
                reason="已阻断，返回 410，不再允许绕过 Governance 执行旧 CEO+Codex 流程",
                replacement="/governance/run"),
    RoutePolicy(path="/workflows/dag/run", methods=["POST"], category="deprecated",
                requires_governance=True, has_guard=True, owner="workflow",
                reason="已阻断，返回 410，不再允许绕过 Governance 执行 DAG 同步工作流",
                replacement="/governance/run"),
    RoutePolicy(path="/workflows/dag/run-async", methods=["POST"], category="deprecated",
                requires_governance=True, has_guard=True, owner="workflow",
                reason="已阻断，返回 410，不再允许绕过 Governance 执行 DAG 异步工作流",
                replacement="/governance/run"),
    RoutePolicy(path="/templates/run/{template_id}", methods=["POST"], category="deprecated",
                requires_governance=True, has_guard=True, owner="template",
                reason="已阻断，返回 410，模板多 Agent 执行旧入口已停用，需迁移为受控 capability",
                replacement=None),
    RoutePolicy(path="/commander/sessions/{session_id}/continue", methods=["POST"], category="deprecated",
                requires_governance=True, has_guard=True, owner="commander",
                reason="已阻断，返回 410，Commander 旧会话继续执行已停用，避免恢复旧编排绕过 Governance",
                replacement="/governance/run"),

    # ── high_risk: 高风险执行入口，未接入 Governance ──────
    RoutePolicy(path="/boss/missions/from-template", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="boss",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/boss/missions", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="boss",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/boss/missions/{mission_id}/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="boss",
                reason="已接入 Governance Guard，读取 mission goal 后拦截不支持目标"),
    RoutePolicy(path="/boss/missions/{mission_id}/modules/{module_id}/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="boss",
                reason="已接入 Governance Guard，读取 mission goal 后拦截不支持目标"),
    RoutePolicy(path="/pipeline/execute", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="pipeline",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/ceo/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/codex/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/openclaw/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/qa/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/cto/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/system/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/image/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/marketing/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/video/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/data/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/agents/{agent_id}/execute", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="agents",
                reason="统一执行入口，已接入 Governance Guard，拦截不支持目标"),
    RoutePolicy(path="/marketing/copywriting", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="marketing",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/marketing/social", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="marketing",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/marketing/seo", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="marketing",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/marketing/email", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="marketing",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/marketing/brand-strategy", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="marketing",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/marketing/campaign", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="marketing",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/cto/review", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="cto",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/cto/tech-choice", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="cto",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/cto/architect", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="cto",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/cto/decompose", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="cto",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/cto/estimate", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="cto",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/swarm/chain", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="swarm",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/swarm/fanout", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="swarm",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/swarm/pipeline", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="swarm",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/data/upload", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/data/load", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/data/explore", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/data/clean", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/data/analyze", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/data/viz", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/data/export", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="data",
                reason="已接入 Governance Guard，拦截无目标执行"),
    RoutePolicy(path="/image/generate", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="image",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/image/analyze", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="image",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/plugins/{plugin_id}/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="plugin",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/plugins/{plugin_id}/test", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="plugin_config",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
    RoutePolicy(path="/ai/run", methods=["POST"], category="protected",
                requires_governance=True, has_guard=True, owner="ai_registry",
                reason="已接入 Governance Guard，拦截 unsupported/needs_clarification 目标"),
]


# ── 查询函数 ────────────────────────────────────────────────

def list_route_policies() -> List[RoutePolicy]:
    """返回所有路由策略"""
    return list(_POLICIES)


def get_route_policy(path: str, method: str = "GET") -> Optional[RoutePolicy]:
    """按 path + method 查找路由策略"""
    method_upper = method.upper()
    for policy in _POLICIES:
        if policy.path == path and method_upper in policy.methods:
            return policy
    return None


def is_route_controlled(path: str, method: str) -> bool:
    """检查路由是否为受控入口"""
    policy = get_route_policy(path, method)
    return policy is not None and policy.category == "controlled"


def routes_requiring_guard() -> List[RoutePolicy]:
    """返回尚未受治理保护的旧/高风险执行入口（不含 controlled 入口）。
    兼容旧调用，内部委托 routes_unprotected_execution()。"""
    return routes_unprotected_execution()


def routes_unprotected_execution() -> List[RoutePolicy]:
    """返回真正需要处理的执行入口：category 为 high_risk 或 deprecated，且 has_guard=False。"""
    return [
        p for p in _POLICIES
        if p.category in ("high_risk", "deprecated")
        and p.requires_governance
        and not p.has_guard
    ]


def routes_controlled_entrypoints() -> List[RoutePolicy]:
    """返回 category=controlled 且 requires_governance=True 的受控入口。"""
    return [
        p for p in _POLICIES
        if p.category == "controlled" and p.requires_governance
    ]


def routes_high_risk_without_guard() -> List[RoutePolicy]:
    """只返回 category=high_risk 且 requires_governance=true 且 has_guard=false 的路由"""
    return [
        p for p in _POLICIES
        if p.category == "high_risk" and p.requires_governance and not p.has_guard
    ]


def routes_deprecated_without_guard() -> List[RoutePolicy]:
    """只返回 category=deprecated 且 requires_governance=true 且 has_guard=false 的路由"""
    return [
        p for p in _POLICIES
        if p.category == "deprecated" and p.requires_governance and not p.has_guard
    ]


def _normalize_path(path: str) -> str:
    """将 FastAPI 路径参数统一化，用于模糊比较。

    例如 /boss/missions/{mission_id}/run → /boss/missions/{id}/run
    """
    import re
    return re.sub(r"\{[^}]+\}", "{id}", path)


def find_unclassified_routes(app=None) -> List[Dict]:
    """
    如果传入 FastAPI app，从 app.routes 中扫描实际路由，
    找出未在 registry 中登记的路由。

    同时考虑 path 和 HTTP method：
    - 如果 registry 只有 GET /xxx，但 app 新增 POST /xxx，判定为 unclassified。
    - 支持路径参数归一化匹配。
    - 内置文档/静态路由自动忽略。
    """
    if app is None:
        return []

    # 构建已登记的 (path, method) 集合（含归一化版本）
    registered = set()
    registered_normalized = set()
    for p in _POLICIES:
        for m in p.methods:
            registered.add((p.path, m.upper()))
            registered_normalized.add((_normalize_path(p.path), m.upper()))

    # 忽略内置文档/静态路由
    _IGNORED_PREFIXES = ("/docs", "/redoc", "/openapi", "/assets", "/app", "/ws")

    unclassified = []
    for route in app.routes:
        if not hasattr(route, "path"):
            continue
        path = route.path
        methods = list(route.methods) if hasattr(route, "methods") and route.methods else ["GET"]

        # 忽略内置路由
        if any(path.startswith(prefix) for prefix in _IGNORED_PREFIXES):
            continue
        if path == "/":
            continue

        # 检查每个 HTTP method 是否已登记
        for method in methods:
            method_upper = method.upper()
            # 跳过 HEAD（通常跟随 GET）
            if method_upper == "HEAD":
                continue

            # 精确匹配 (path, method)
            if (path, method_upper) in registered:
                continue

            # 归一化匹配
            if (_normalize_path(path), method_upper) in registered_normalized:
                continue

            unclassified.append({
                "path": path,
                "methods": [method_upper],
                "reason": "未在 Route Policy Registry 中登记",
            })

    return unclassified
