"""
Boss Command Center Service — 通用业务流程执行引擎

职责：
1. 创建 Mission（通用模块化流程，支持 enabled_modules 选择性执行）
2. 执行单个模块 / 整个 Mission
3. 持久化 Mission 结果（含进度字段 started_at/finished_at/duration_ms）
4. 查询 Mission 历史
5. 导出 Mission 报告（JSON / Markdown）
6. 事件日志（mission_created/started/succeeded/failed, module_*, exported）

设计原则：
- 系统核心适配所有业务流程，不绑定任何具体行业
- 业务差异通过用户输入、模板参数、上下文 schema、审核清单体现
- 具体行业模板只能作为 example 或 alias，不能成为核心默认架构
"""
import uuid
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.database.database import get_db
from backend.logger import get_logger

logger = get_logger()

# ── 模块定义（通用业务能力，不绑定具体行业） ──────────────
MODULE_DEFINITIONS = {
    "strategy": {
        "title": "目标理解与策略判断",
        "description": "理解用户目标，提取核心意图，给出策略判断、关键机会和风险。",
        "prompt_template": (
            "请作为业务策略顾问，围绕以下目标进行分析和判断：{goal}\n\n"
            "要求包含：\n"
            "1. 目标解读：用户真正想要达成什么\n"
            "2. 核心机会：当前最值得关注的切入点\n"
            "3. 主要风险：可能遇到的障碍和不确定性\n"
            "4. 优先级建议：应该先做什么、后做什么"
        ),
    },
    "market": {
        "title": "上下文与证据整理",
        "description": "围绕目标收集相关上下文、事实依据、参考案例和数据支撑。",
        "prompt_template": (
            "请围绕以下目标收集和整理相关上下文信息：{goal}\n\n"
            "要求包含：\n"
            "1. 相关背景：与目标相关的行业/市场/用户现状\n"
            "2. 参考案例：类似目标的成功/失败案例\n"
            "3. 关键数据：支撑判断的事实和数据\n"
            "4. 差异化机会：未被充分覆盖的切入点"
        ),
    },
    "marketing": {
        "title": "沟通与触达方案",
        "description": "围绕目标设计沟通策略、内容方向、触达渠道和具体文案。",
        "prompt_template": (
            "请围绕以下目标设计沟通与触达方案：{goal}\n\n"
            "要求包含：\n"
            "1. 目标受众：需要触达的人群及其特征\n"
            "2. 核心信息：最想传递的 1-3 个关键点\n"
            "3. 触达渠道：推荐的沟通渠道和方式\n"
            "4. 内容方案：3-5 条可直接使用的内容/文案"
        ),
    },
    "landing": {
        "title": "交付物结构",
        "description": "围绕目标设计可交付物的结构、框架和核心内容。",
        "prompt_template": (
            "请围绕以下目标设计一个交付物结构：{goal}\n\n"
            "要求包含：\n"
            "1. 整体结构：交付物的章节/模块划分\n"
            "2. 核心模块：每个模块的目的和关键内容\n"
            "3. 信任支撑：增强说服力的证据或案例\n"
            "4. 行动引导：用户下一步应该做什么"
        ),
    },
    "actions": {
        "title": "执行计划",
        "description": "将目标拆解为可执行的行动项，按时间或优先级排列。",
        "prompt_template": (
            "请围绕以下目标制定执行计划：{goal}\n\n"
            "要求包含：\n"
            "1. 立即行动：今天就能开始做的事项\n"
            "2. 短期计划：本周需要完成的关键任务\n"
            "3. 中期规划：本月需要推进的重点工作\n"
            "4. 验收标准：每项任务的完成标志和检查方式"
        ),
    },
}

MODULE_ORDER = ["strategy", "market", "marketing", "landing", "actions"]

# Phase 6.16: 模块级执行超时（秒）
MODULE_TIMEOUT_SECONDS = {
    "strategy": 60,
    "market": 90,
    "marketing": 90,
    "landing": 60,
    "actions": 60,
}
MODULE_TIMEOUT_DEFAULT = 60

# ── 通用业务流程模板 ─────────────────────────────────────
# 系统核心适配所有业务流程，业务差异通过模板参数体现。
# 具体行业/场景只能作为 example 或 alias，不能成为核心默认架构。

PROTOCOL_VERSION = "1.0"

MISSION_TEMPLATES = [
    {
        "id": "goal_to_plan",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "目标到计划",
        "description": "从一个业务目标出发，产出策略判断、上下文分析、执行计划。",
        "default_goal": "我有一个业务目标需要拆解成可执行计划",
        "default_modules": ["strategy", "market", "actions"],
        "suggested_inputs": ["目标描述", "可用资源", "时间约束"],
        "expected_outputs": ["策略判断", "关键依据", "执行计划"],
        "input_fields": [
            {"name": "goal_description", "label": "目标描述", "type": "text", "required": True, "placeholder": "例：本月把用户转化率从 2% 提升到 5%"},
            {"name": "resources", "label": "可用资源（可选）", "type": "text", "required": False, "placeholder": "例：3 人团队、5 万预算"},
            {"name": "timeline", "label": "时间约束（可选）", "type": "text", "required": False, "placeholder": "例：2 周内"},
        ],
        "context_schema": {
            "fields": ["goal_description", "resources", "timeline", "constraints"],
            "description": "用户目标、可用资源、时间线和约束条件",
        },
        "review_checklist": [
            "策略判断是否基于充分的事实依据",
            "执行计划是否考虑了资源和时间约束",
            "任务拆解粒度是否足够可执行",
            "验收标准是否清晰可衡量",
        ],
    },
    {
        "id": "research_to_decision",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "调研到决策",
        "description": "围绕一个决策问题，收集上下文、分析选项、给出建议。",
        "default_goal": "我需要做一个业务决策，希望先收集充分的信息和分析",
        "default_modules": ["strategy", "market", "marketing", "actions"],
        "suggested_inputs": ["决策问题", "备选方案", "关键顾虑"],
        "expected_outputs": ["决策框架", "方案对比", "推荐建议", "行动计划"],
        "input_fields": [
            {"name": "decision_question", "label": "决策问题", "type": "text", "required": True, "placeholder": "例：应该先做国内市场还是出海"},
            {"name": "alternatives", "label": "备选方案（可选）", "type": "text", "required": False, "placeholder": "例：方案A做小红书，方案B做抖音"},
            {"name": "concerns", "label": "关键顾虑（可选）", "type": "text", "required": False, "placeholder": "例：预算有限，怕选错方向"},
        ],
        "context_schema": {
            "fields": ["decision_question", "alternatives", "concerns", "decision_criteria"],
            "description": "决策问题、备选方案、顾虑和决策标准",
        },
        "review_checklist": [
            "调研是否覆盖了足够多的信息来源",
            "方案对比维度是否全面",
            "推荐建议是否有充分的数据支撑",
            "风险提示是否到位",
        ],
    },
    {
        "id": "deliverable_pack",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "交付物生成",
        "description": "围绕一个交付目标，产出结构化的内容、文案或文档。",
        "default_goal": "我需要生成一套完整的交付物",
        "default_modules": ["strategy", "marketing", "landing", "actions"],
        "suggested_inputs": ["交付物类型", "目标受众", "核心要求"],
        "expected_outputs": ["内容框架", "核心内容", "质量检查", "发布/交付清单"],
        "input_fields": [
            {"name": "deliverable_type", "label": "交付物类型", "type": "text", "required": True, "placeholder": "例：产品介绍文档、推广文案包、项目方案"},
            {"name": "target_audience", "label": "目标受众", "type": "text", "required": True, "placeholder": "例：潜在客户、投资人、团队成员"},
            {"name": "key_requirements", "label": "核心要求（可选）", "type": "text", "required": False, "placeholder": "例：专业严谨、轻松活泼、突出数据"},
        ],
        "context_schema": {
            "fields": ["deliverable_type", "target_audience", "key_requirements", "tone"],
            "description": "交付物类型、受众、要求和风格",
        },
        "review_checklist": [
            "内容是否符合目标受众的需求和理解水平",
            "核心信息是否清晰、准确、完整",
            "结构是否合理，易于阅读和使用",
            "是否有遗漏的关键内容",
        ],
    },
    {
        "id": "communication_plan",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "沟通与触达方案",
        "description": "围绕一个沟通目标，设计触达策略、内容方向和执行方案。",
        "default_goal": "我需要设计一套沟通触达方案",
        "default_modules": ["strategy", "market", "marketing", "actions"],
        "suggested_inputs": ["沟通目标", "目标人群", "可用渠道"],
        "expected_outputs": ["受众分析", "核心信息", "渠道策略", "内容方案", "执行清单"],
        "input_fields": [
            {"name": "communication_goal", "label": "沟通目标", "type": "text", "required": True, "placeholder": "例：让目标用户了解我们的新产品"},
            {"name": "target_group", "label": "目标人群", "type": "text", "required": True, "placeholder": "例：25-35 岁一线城市白领"},
            {"name": "available_channels", "label": "可用渠道（可选）", "type": "text", "required": False, "placeholder": "例：微信公众号、小红书、线下活动"},
        ],
        "context_schema": {
            "fields": ["communication_goal", "target_group", "available_channels", "budget"],
            "description": "沟通目标、目标人群、可用渠道和预算",
        },
        "review_checklist": [
            "目标人群画像是否清晰",
            "核心信息是否简洁有力",
            "渠道选择是否匹配目标人群习惯",
            "内容方案是否可直接执行",
        ],
    },
    {
        "id": "operation_review",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "流程复盘",
        "description": "对已完成的工作或项目进行复盘，总结经验教训，产出改进计划。",
        "default_goal": "我需要对上一阶段的工作进行复盘",
        "default_modules": ["strategy", "market", "actions"],
        "suggested_inputs": ["复盘周期", "关键数据", "遇到的问题"],
        "expected_outputs": ["成果总结", "问题诊断", "经验教训", "改进计划"],
        "input_fields": [
            {"name": "review_period", "label": "复盘周期", "type": "text", "required": True, "placeholder": "例：上个月、上季度、最近一次活动"},
            {"name": "key_data", "label": "关键数据（可选）", "type": "text", "required": False, "placeholder": "例：GMV 50万，转化率 3.2%，退货率 5%"},
            {"name": "issues_encountered", "label": "遇到的问题（可选）", "type": "text", "required": False, "placeholder": "例：获客成本上升、复购率下降"},
        ],
        "context_schema": {
            "fields": ["review_period", "key_data", "issues_encountered", "goals_next_period"],
            "description": "复盘周期、关键数据、遇到的问题和下阶段目标",
        },
        "review_checklist": [
            "成果总结是否基于客观数据",
            "问题诊断是否找到了根本原因",
            "经验教训是否可复用",
            "改进计划是否具体可执行",
        ],
    },
    {
        "id": "risk_check",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "风险检查",
        "description": "对一个计划或决策进行风险评估，识别潜在问题并给出应对方案。",
        "default_goal": "我需要对当前计划进行风险检查",
        "default_modules": ["strategy", "market", "actions"],
        "suggested_inputs": ["计划概述", "已知风险", "最担心的事"],
        "expected_outputs": ["风险清单", "影响评估", "应对方案", "监控指标"],
        "input_fields": [
            {"name": "plan_overview", "label": "计划概述", "type": "text", "required": True, "placeholder": "例：下月上线新功能，预计投入 3 人 2 周"},
            {"name": "known_risks", "label": "已知风险（可选）", "type": "text", "required": False, "placeholder": "例：技术方案不确定、竞品可能抢先"},
            {"name": "top_concern", "label": "最担心的事（可选）", "type": "text", "required": False, "placeholder": "例：上线后用户不买账"},
        ],
        "context_schema": {
            "fields": ["plan_overview", "known_risks", "top_concern", "risk_tolerance"],
            "description": "计划概述、已知风险、最大顾虑和风险承受度",
        },
        "review_checklist": [
            "风险清单是否全面，覆盖技术/市场/执行/合规等维度",
            "影响评估是否区分了概率和严重程度",
            "应对方案是否具体可操作",
            "监控指标是否可实时跟踪",
        ],
    },
    {
        "id": "execution_checklist",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "执行清单",
        "description": "将一个复杂任务拆解为详细的执行清单，含步骤、检查项和验收标准。",
        "default_goal": "我需要一份详细的执行清单来推进工作",
        "default_modules": ["strategy", "actions"],
        "suggested_inputs": ["任务描述", "交付标准", "截止时间"],
        "expected_outputs": ["执行步骤", "检查清单", "验收标准"],
        "input_fields": [
            {"name": "task_description", "label": "任务描述", "type": "text", "required": True, "placeholder": "例：完成产品 v2.0 的上线发布"},
            {"name": "delivery_criteria", "label": "交付标准（可选）", "type": "text", "required": False, "placeholder": "例：无 P0 bug、文档齐全、灰度放量"},
            {"name": "deadline", "label": "截止时间（可选）", "type": "text", "required": False, "placeholder": "例：本月底"},
        ],
        "context_schema": {
            "fields": ["task_description", "delivery_criteria", "deadline", "dependencies"],
            "description": "任务描述、交付标准、截止时间和依赖关系",
        },
        "review_checklist": [
            "执行步骤是否按正确顺序排列",
            "每步是否有明确的完成标志",
            "检查清单是否覆盖所有关键环节",
            "验收标准是否可量化",
        ],
    },
    {
        "id": "data_insight",
        "protocol_version": PROTOCOL_VERSION,
        "template_type": "generic_business_process",
        "domain_lock": False,
        "name": "数据洞察",
        "description": "围绕一组数据或指标，进行分析、发现问题、给出行动建议。",
        "default_goal": "我需要从数据中找到关键洞察和行动方向",
        "default_modules": ["strategy", "market", "actions"],
        "suggested_inputs": ["数据来源", "关注指标", "分析目标"],
        "expected_outputs": ["数据解读", "关键发现", "行动建议"],
        "input_fields": [
            {"name": "data_source", "label": "数据来源/内容", "type": "text", "required": True, "placeholder": "例：上月销售数据、用户行为日志、问卷结果"},
            {"name": "focus_metrics", "label": "关注指标（可选）", "type": "text", "required": False, "placeholder": "例：转化率、留存率、ARPU"},
            {"name": "analysis_goal", "label": "分析目标（可选）", "type": "text", "required": False, "placeholder": "例：找出流失原因、发现增长机会"},
        ],
        "context_schema": {
            "fields": ["data_source", "focus_metrics", "analysis_goal", "time_range"],
            "description": "数据来源、关注指标、分析目标和时间范围",
        },
        "review_checklist": [
            "数据解读是否准确，无误导性结论",
            "关键发现是否基于充分的数据支撑",
            "行动建议是否具体可执行",
            "是否考虑了数据的局限性",
        ],
    },
]

# ── 旧业务模板 ID 兼容映射 ───────────────────────────────
# 旧 ID 可正常创建 mission，但映射到通用模板协议。
TEMPLATE_ALIASES = {
    "ecommerce_product_research": "research_to_decision",
    "xianyu_listing_pack": "deliverable_pack",
    "saas_feature_planning": "goal_to_plan",
    "landing_page_offer": "deliverable_pack",
    "weekly_business_review": "operation_review",
    "xianyu_delivery_pack": "deliverable_pack",
}


def _init_boss_tables():
    """建表（幂等）— 含进度字段"""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS boss_missions (
                mission_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
                template_id TEXT DEFAULT '',
                status TEXT DEFAULT 'pending',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime'))
            )
        """)
        db.execute("""
            CREATE TABLE IF NOT EXISTS boss_mission_modules (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                module_id TEXT NOT NULL,
                title TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                prompt TEXT,
                result TEXT,
                confidence REAL DEFAULT 0.0,
                warnings TEXT DEFAULT '[]',
                error TEXT DEFAULT '',
                used_tools TEXT DEFAULT '[]',
                used_agents TEXT DEFAULT '[]',
                mode TEXT DEFAULT '',
                next_actions TEXT DEFAULT '[]',
                structured_output TEXT DEFAULT '{}',
                started_at TEXT,
                finished_at TEXT,
                duration_ms INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (mission_id) REFERENCES boss_missions(mission_id)
            )
        """)
        # 尝试添加新列（已存在的表不会报错）
        for col in (
            "next_actions TEXT DEFAULT '[]'",
            "structured_output TEXT DEFAULT '{}'",
            "started_at TEXT",
            "finished_at TEXT",
            "duration_ms INTEGER DEFAULT 0",
        ):
            try:
                db.execute(f"ALTER TABLE boss_mission_modules ADD COLUMN {col}")
            except Exception:
                pass
        # boss_missions 新列
        for col in ("template_id TEXT DEFAULT ''",):
            try:
                db.execute(f"ALTER TABLE boss_missions ADD COLUMN {col}")
            except Exception:
                pass
        try:
            db.execute("ALTER TABLE boss_missions ADD COLUMN allow_browser_automation TEXT DEFAULT '0'")
        except Exception:
            pass
        db.execute("""
            CREATE TABLE IF NOT EXISTS boss_mission_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                mission_id TEXT NOT NULL,
                type TEXT NOT NULL,
                module_id TEXT,
                message TEXT NOT NULL,
                payload TEXT DEFAULT '{}',
                created_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (mission_id) REFERENCES boss_missions(mission_id)
            )
        """)
        db.commit()


# 启动时建表
try:
    _init_boss_tables()
except Exception:
    pass


class BossCommandCenterService:
    """老板运营指挥台服务"""

    def __init__(self):
        self._runtime = None

    def _get_runtime(self):
        """延迟加载 LocalAgentRuntime"""
        if self._runtime is None:
            from backend.services.local_agent_runtime import get_local_agent_runtime
            self._runtime = get_local_agent_runtime()
        return self._runtime

    # ── 事件日志 ──────────────────────────────────────────

    def _log_event(self, mission_id: str, event_type: str, message: str,
                   module_id: str = None, payload: dict = None):
        """写入事件日志"""
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute(
                "INSERT INTO boss_mission_events (mission_id, type, module_id, message, payload, created_at) VALUES (?, ?, ?, ?, ?, ?)",
                (mission_id, event_type, module_id, message, json.dumps(payload or {}, ensure_ascii=False), now)
            )
            db.commit()

    def get_events(self, mission_id: str) -> List[Dict[str, Any]]:
        """获取 Mission 的事件列表（时间升序）"""
        with get_db() as db:
            rows = db.execute(
                "SELECT * FROM boss_mission_events WHERE mission_id = ? ORDER BY id ASC",
                (mission_id,)
            ).fetchall()
        events = []
        for row in rows:
            evt = dict(row)
            try:
                evt["payload"] = json.loads(evt.get("payload", "{}"))
            except (json.JSONDecodeError, TypeError):
                evt["payload"] = {}
            events.append(evt)
        return events

    # ── 模板 ──────────────────────────────────────────────

    def get_templates(self) -> List[Dict[str, Any]]:
        """返回所有内置模板"""
        return MISSION_TEMPLATES

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取单个模板（支持旧 ID 别名映射）"""
        # 先查主模板列表
        for tpl in MISSION_TEMPLATES:
            if tpl["id"] == template_id:
                return tpl
        # 再查别名映射
        alias_target = TEMPLATE_ALIASES.get(template_id)
        if alias_target:
            for tpl in MISSION_TEMPLATES:
                if tpl["id"] == alias_target:
                    # 返回副本，id 保持用户传入的值（兼容性）
                    aliased = dict(tpl)
                    aliased["id"] = template_id
                    aliased["aliased_to"] = alias_target
                    return aliased
        return None

    def create_mission_from_template(
        self, template_id: str, goal: str = None,
        enabled_modules: List[str] = None, inputs: Dict[str, str] = None,
        auto_run: bool = False,
        allow_browser_automation: bool = False
    ) -> Dict[str, Any]:
        """根据模板创建 Mission"""
        template = self.get_template(template_id)
        if not template:
            return None

        # Phase 6.20: 解析 canonical 模板 ID — 旧 alias 不得泄漏到 mission.template_id
        canonical_id = template.get("aliased_to", template_id)
        aliased_from = template_id if template.get("aliased_to") else None

        # 使用模板默认值，允许 overrides
        actual_goal = goal or template["default_goal"]
        actual_modules = enabled_modules or template["default_modules"]

        # 将 inputs 追加到 goal 中（如果有）
        if inputs:
            inputs_text = "；".join(f"{k}: {v}" for k, v in inputs.items() if v)
            if inputs_text:
                actual_goal = f"{actual_goal}\n\n补充信息：{inputs_text}"

        mission = self.create_mission(actual_goal, auto_run=auto_run, enabled_modules=actual_modules,
                                       template_id=canonical_id, allow_browser_automation=allow_browser_automation)

        # Phase 6.20: 如果是旧 alias，记录来源信息到事件（不影响执行逻辑）
        if aliased_from:
            self._log_event(mission["mission_id"], "template_aliased",
                            f"旧模板 ID '{aliased_from}' 已映射到通用模板 '{canonical_id}'",
                            payload={"aliased_from": aliased_from, "canonical_id": canonical_id})

        return mission

    # ── 指标 ──────────────────────────────────────────────

    def _compute_metrics(self, mission: Dict[str, Any]) -> Dict[str, Any]:
        """计算 Mission 复盘指标"""
        modules = mission.get("modules", [])
        total = len(modules)
        succeeded = sum(1 for m in modules if m.get("status") == "done")
        failed = sum(1 for m in modules if m.get("status") == "failed")
        skipped = sum(1 for m in modules if m.get("status") == "skipped")
        interrupted = sum(1 for m in modules if m.get("status") == "interrupted")
        active = total - skipped
        completion_rate = succeeded / active if active > 0 else 0.0

        duration_ms = sum(m.get("duration_ms", 0) for m in modules if m.get("duration_ms"))
        warning_count = sum(len(m.get("warnings", [])) for m in modules)
        next_action_count = sum(len(m.get("next_actions", [])) for m in modules)

        return {
            "total_modules": total,
            "succeeded_modules": succeeded,
            "failed_modules": failed,
            "skipped_modules": skipped,
            "interrupted_modules": interrupted,
            "duration_ms": duration_ms,
            "warning_count": warning_count,
            "next_action_count": next_action_count,
            "completion_rate": round(completion_rate, 2),
        }

    def _update_mission_status_from_modules(self, mission_id: str):
        """根据所有模块状态更新 Mission 整体状态（v2：人工审核闭环语义）"""
        mission = self.get_mission(mission_id)
        if not mission:
            return

        active_modules = [m for m in mission["modules"] if m["status"] != "skipped"]
        if not active_modules:
            return

        all_done = all(m["status"] == "done" for m in active_modules)
        any_failed = any(m["status"] == "failed" for m in active_modules)
        any_running = any(m["status"] == "running" for m in active_modules)
        any_interrupted = any(m["status"] == "interrupted" for m in active_modules)
        has_any_result = any(
            m.get("result") and len(m.get("result", "").strip()) >= 10
            for m in active_modules
        )

        if any_running:
            self._update_mission_status(mission_id, "running")
        elif any_interrupted:
            # 有中断模块：根据是否有结果决定 partial 或 interrupted
            if has_any_result:
                self._update_mission_status(mission_id, "partial")
                self._log_event(mission_id, "mission_partial", "部分模块有结果，部分中断，等待人工处理")
            else:
                self._update_mission_status(mission_id, "interrupted")
                self._log_event(mission_id, "mission_interrupted", "执行中断，无有效结果，可重跑")
        elif has_any_result:
            if all_done:
                self._update_mission_status(mission_id, "ready_for_review")
                self._log_event(mission_id, "mission_ready", "所有模块执行完成，等待人工审核")
            else:
                self._update_mission_status(mission_id, "partial")
                self._log_event(mission_id, "mission_partial", "部分模块有结果，等待人工审核")
        elif any_failed:
            self._update_mission_status(mission_id, "failed")
            self._log_event(mission_id, "mission_failed", "所有模块均无有效结果")
        else:
            # 全部 pending 状态
            self._update_mission_status(mission_id, "pending_review")

    # ── Mission CRUD ──────────────────────────────────────

    def create_mission(self, goal: str, auto_run: bool = False,
                       enabled_modules: List[str] = None,
                       template_id: str = "",
                       allow_browser_automation: bool = False) -> Dict[str, Any]:
        """创建 Mission

        Args:
            goal: 业务目标
            auto_run: 创建后是否立即执行
            enabled_modules: 启用的模块 ID 列表，None 表示全部启用
            template_id: 模板 ID（可选）
            allow_browser_automation: 是否允许浏览器自动化采集
        """
        mission_id = f"mission_{uuid.uuid4().hex[:8]}"
        now = datetime.now().isoformat()

        # 确定启用的模块
        if enabled_modules is None:
            active_modules = MODULE_ORDER
        else:
            # 验证模块 ID
            active_modules = [m for m in enabled_modules if m in MODULE_ORDER]
            if not active_modules:
                active_modules = MODULE_ORDER

        with get_db() as db:
            db.execute(
                "INSERT INTO boss_missions (mission_id, goal, template_id, status, created_at, updated_at, allow_browser_automation) VALUES (?, ?, ?, 'pending_review', ?, ?, ?)",
                (mission_id, goal, template_id, now, now, json.dumps(allow_browser_automation))
            )
            # Phase 6.19: 查找模板 prompt_overrides
            template = self.get_template(template_id) if template_id else None
            prompt_overrides = template.get("prompt_overrides", {}) if template else {}

            for module_id in MODULE_ORDER:
                definition = MODULE_DEFINITIONS[module_id]
                # Phase 6.19: 优先使用模板的 prompt_overrides
                if module_id in prompt_overrides:
                    prompt = prompt_overrides[module_id].format(goal=goal)
                else:
                    prompt = definition["prompt_template"].format(goal=goal)

                if module_id in active_modules:
                    status = "pending"
                else:
                    status = "skipped"

                db.execute(
                    """INSERT INTO boss_mission_modules
                       (mission_id, module_id, title, status, prompt, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (mission_id, module_id, definition["title"], status, prompt, now, now)
                )
            db.commit()

        logger.info(f"BossCommandCenter: Created mission {mission_id} for goal: {goal[:60]}")
        self._log_event(mission_id, "mission_created", f"创建任务: {goal[:60]}",
                        payload={"enabled_modules": active_modules,
                                 "auto_run": auto_run,
                                 "allow_browser_automation": allow_browser_automation})
        for module_id in MODULE_ORDER:
            if module_id not in active_modules:
                self._log_event(mission_id, "module_skipped", f"模块 {MODULE_DEFINITIONS[module_id]['title']} 已跳过（未启用）",
                                module_id=module_id)
        mission = self.get_mission(mission_id)

        # v2: auto_run is deprecated — mission always stays in pending_review after creation.
        # Callers must explicitly call run_mission() to execute.
        # The auto_run parameter is accepted for API compatibility but ignored.

        return mission

    def list_missions(self, limit: int = 20, offset: int = 0) -> List[Dict[str, Any]]:
        """列出 Mission"""
        with get_db() as db:
            rows = db.execute(
                "SELECT mission_id, goal, status, created_at, updated_at FROM boss_missions ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
        return [dict(row) for row in rows]

    def get_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """获取 Mission 详情（含 modules）"""
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM boss_missions WHERE mission_id = ?", (mission_id,)
            ).fetchone()
            if not row:
                return None
            mission = dict(row)
            # Parse allow_browser_automation JSON boolean
            try:
                mission["allow_browser_automation"] = json.loads(mission.get("allow_browser_automation", "false"))
            except (json.JSONDecodeError, TypeError):
                mission["allow_browser_automation"] = False

            modules = db.execute(
                "SELECT * FROM boss_mission_modules WHERE mission_id = ? ORDER BY id",
                (mission_id,)
            ).fetchall()
            mission["modules"] = []
            for m in modules:
                mod = dict(m)
                # 解析 JSON 字段
                for field in ("warnings", "used_tools", "used_agents", "next_actions"):
                    try:
                        mod[field] = json.loads(mod.get(field, "[]"))
                    except (json.JSONDecodeError, TypeError):
                        mod[field] = []
                # 解析 structured_output
                try:
                    mod["structured_output"] = json.loads(mod.get("structured_output", "{}"))
                except (json.JSONDecodeError, TypeError):
                    mod["structured_output"] = {}
                mission["modules"].append(mod)

            # 动态计算 metrics
            mission["metrics"] = self._compute_metrics(mission)

            return mission

    # ── 执行 ──────────────────────────────────────────────

    def accept_mission(self, mission_id: str, comment: str = "") -> Optional[Dict[str, Any]]:
        """用户确认接受 Mission 结果，状态改为 done"""
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        if mission["status"] not in ("ready_for_review", "partial", "interrupted"):
            logger.warning(f"Cannot accept mission {mission_id} in status {mission['status']}")
            return mission

        self._update_mission_status(mission_id, "done")
        self._log_event(mission_id, "mission_accepted",
                        f"用户接受结果" + (f": {comment}" if comment else ""),
                        payload={"comment": comment})
        logger.info(f"BossCommandCenter: Mission {mission_id} accepted by user")
        return self.get_mission(mission_id)

    # ── 僵尸状态清理 ──────────────────────────────────────

    def cleanup_stale_running_missions(self, timeout_minutes: int = 30) -> Dict[str, Any]:
        """清理超时的 running 状态模块和任务

        规则：
        - running 超过 timeout_minutes 的模块：
          - 有 result 内容 → partial（保留已有结果）
          - 无 result → interrupted
        - 写入 warning：上次执行可能中断，请人工重跑
        - 更新 mission 状态
        - 不会删除任何 mission/module，不会清空 result

        Returns:
            {"cleaned_modules": int, "affected_missions": list[str], "details": list[dict]}
        """
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(minutes=timeout_minutes)).isoformat()
        cleaned_modules = []
        affected_missions = set()
        events_to_log = []

        with get_db() as db:
            # 找到超时的 running 模块
            stale_rows = db.execute(
                """SELECT mission_id, module_id, result, warnings
                   FROM boss_mission_modules
                   WHERE status = 'running' AND started_at IS NOT NULL AND started_at < ?""",
                (cutoff,)
            ).fetchall()

            for row in stale_rows:
                mid = row["mission_id"]
                mod_id = row["module_id"]
                existing_result = row["result"] or ""
                try:
                    existing_warnings = json.loads(row["warnings"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    existing_warnings = []

                # 判断新状态
                has_result = len(existing_result.strip()) >= 10
                new_status = "partial" if has_result else "interrupted"

                # 追加中断警告
                interrupt_warning = "上次执行可能中断，请人工检查或重跑该模块"
                if interrupt_warning not in existing_warnings:
                    existing_warnings.append(interrupt_warning)

                now = datetime.now().isoformat()
                db.execute(
                    """UPDATE boss_mission_modules
                       SET status = ?, warnings = ?, updated_at = ?
                       WHERE mission_id = ? AND module_id = ?""",
                    (new_status, json.dumps(existing_warnings, ensure_ascii=False),
                     now, mid, mod_id)
                )

                cleaned_modules.append({
                    "mission_id": mid,
                    "module_id": mod_id,
                    "old_status": "running",
                    "new_status": new_status,
                    "has_result": has_result,
                })
                affected_missions.add(mid)

                events_to_log.append({
                    "mission_id": mid,
                    "event_type": "module_interrupted",
                    "message": f"模块 {MODULE_DEFINITIONS.get(mod_id, {}).get('title', mod_id)} 执行超时，已标记为 {new_status}",
                    "module_id": mod_id,
                    "payload": {"timeout_minutes": timeout_minutes, "new_status": new_status},
                })

            db.commit()

        # 记录事件（在事务外调用，避免嵌套数据库锁）
        for evt in events_to_log:
            self._log_event(evt["mission_id"], evt["event_type"], evt["message"],
                            module_id=evt["module_id"], payload=evt["payload"])

        # 更新受影响的 mission 状态
        for mid in affected_missions:
            self._update_mission_status_from_modules(mid)

        # 记录全局清理事件
        if cleaned_modules:
            logger.info(f"BossCommandCenter: Cleaned {len(cleaned_modules)} stale running modules "
                        f"across {len(affected_missions)} missions")
            for mid in affected_missions:
                self._log_event(mid, "stale_running_cleaned",
                                f"清理了 {sum(1 for c in cleaned_modules if c['mission_id'] == mid)} 个超时 running 模块",
                                payload={"timeout_minutes": timeout_minutes})

        return {
            "cleaned_modules": len(cleaned_modules),
            "affected_missions": list(affected_missions),
            "details": cleaned_modules,
        }

    def cleanup_mission_stale_modules(self, mission_id: str, timeout_minutes: int = 5) -> int:
        """轻量清理单个 mission 中的 stale running 模块

        在 run_mission 开始前调用，避免重复执行卡死状态。
        timeout 较短（默认 5 分钟），因为是同次会话内的清理。

        Returns:
            清理的模块数量
        """
        from datetime import timedelta

        cutoff = (datetime.now() - timedelta(minutes=timeout_minutes)).isoformat()
        cleaned = 0
        events_to_log = []

        with get_db() as db:
            stale_rows = db.execute(
                """SELECT module_id, result, warnings
                   FROM boss_mission_modules
                   WHERE mission_id = ? AND status = 'running'
                     AND started_at IS NOT NULL AND started_at < ?""",
                (mission_id, cutoff)
            ).fetchall()

            for row in stale_rows:
                mod_id = row["module_id"]
                existing_result = row["result"] or ""
                try:
                    existing_warnings = json.loads(row["warnings"] or "[]")
                except (json.JSONDecodeError, TypeError):
                    existing_warnings = []

                has_result = len(existing_result.strip()) >= 10
                new_status = "partial" if has_result else "interrupted"

                interrupt_warning = "上次执行可能中断，请人工检查或重跑该模块"
                if interrupt_warning not in existing_warnings:
                    existing_warnings.append(interrupt_warning)

                now = datetime.now().isoformat()
                db.execute(
                    """UPDATE boss_mission_modules
                       SET status = ?, warnings = ?, updated_at = ?
                       WHERE mission_id = ? AND module_id = ?""",
                    (new_status, json.dumps(existing_warnings, ensure_ascii=False),
                     now, mission_id, mod_id)
                )
                cleaned += 1

                events_to_log.append({
                    "event_type": "module_interrupted",
                    "message": f"模块 {MODULE_DEFINITIONS.get(mod_id, {}).get('title', mod_id)} 执行超时，已标记为 {new_status}",
                    "module_id": mod_id,
                    "payload": {"timeout_minutes": timeout_minutes, "new_status": new_status},
                })

            db.commit()

        for evt in events_to_log:
            self._log_event(mission_id, evt["event_type"], evt["message"],
                            module_id=evt["module_id"], payload=evt["payload"])

        if cleaned > 0:
            self._update_mission_status_from_modules(mission_id)

        return cleaned

    def run_mission(self, mission_id: str, allow_browser_automation: bool = None) -> Optional[Dict[str, Any]]:
        """执行整个 Mission（顺序执行，跳过 skipped 模块）

        Args:
            mission_id: Mission ID
            allow_browser_automation: 是否允许浏览器自动化采集。
                None (default) → use the saved mission value.
        """
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        # Default to the saved mission flag when caller did not explicitly pass it
        if allow_browser_automation is None:
            allow_browser_automation = mission.get("allow_browser_automation", False)

        # 轻量清理当前 mission 中的 stale running 模块（避免重复执行卡死状态）
        stale_count = self.cleanup_mission_stale_modules(mission_id, timeout_minutes=5)
        if stale_count > 0:
            logger.info(f"BossCommandCenter: Cleaned {stale_count} stale modules before running mission {mission_id}")
            mission = self.get_mission(mission_id)

        # Phase 6.28: 原子 CAS 确保同一 mission 不会被并发执行
        # 只有 status != 'running' 时才能转为 'running'
        now = datetime.now().isoformat()
        with get_db() as db:
            cursor = db.execute(
                "UPDATE boss_missions SET status = 'running', updated_at = ? WHERE mission_id = ? AND status != 'running'",
                (now, mission_id)
            )
            db.commit()
            if cursor.rowcount == 0:
                # 已经在 running — 并发冲突
                logger.warning(f"BossCommandCenter: Mission {mission_id} already running, skipping duplicate run_mission")
                return self.get_mission(mission_id)

        self._log_event(mission_id, "mission_started", "开始执行任务")

        for module in mission["modules"]:
            # 跳过已完成或已跳过的模块
            if module["status"] in ("done", "skipped"):
                continue
            result = self.run_module(mission_id, module["module_id"],
                           allow_browser_automation=allow_browser_automation)
            # Phase 6.16: 模块超时/中断后停止后续模块
            if result:
                mod_status = next(
                    (m["status"] for m in result.get("modules", [])
                     if m["module_id"] == module["module_id"]), None
                )
                if mod_status == "interrupted":
                    logger.info(f"BossCommandCenter: Module {module['module_id']} interrupted, stopping remaining modules")
                    break

        # 重新读取并计算最终状态（v2：人工审核闭环语义）
        mission = self.get_mission(mission_id)
        active_modules = [m for m in mission["modules"] if m["status"] != "skipped"]
        if not active_modules:
            self._update_mission_status(mission_id, "pending_review")
            return self.get_mission(mission_id)

        has_any_result = any(m.get("result") and len(m.get("result", "").strip()) >= 10 for m in active_modules)
        all_ok = all(m["status"] == "done" for m in active_modules)
        any_failed = any(m["status"] == "failed" for m in active_modules)
        any_interrupted = any(m["status"] == "interrupted" for m in active_modules)

        if any_interrupted:
            if has_any_result:
                self._update_mission_status(mission_id, "partial")
                self._log_event(mission_id, "mission_partial", "部分模块执行中断，已有结果等待人工审核")
            else:
                self._update_mission_status(mission_id, "interrupted")
                self._log_event(mission_id, "mission_interrupted", "模块执行中断，无有效结果")
        elif has_any_result:
            if all_ok:
                self._update_mission_status(mission_id, "ready_for_review")
                self._log_event(mission_id, "mission_completed", "所有模块执行完成，等待人工审核")
            else:
                self._update_mission_status(mission_id, "partial")
                self._log_event(mission_id, "mission_partial", "部分模块有结果，等待人工审核")
        elif any_failed:
            self._update_mission_status(mission_id, "failed")
            self._log_event(mission_id, "mission_failed", "所有模块均无有效结果")
        else:
            self._update_mission_status(mission_id, "pending_review")
            self._log_event(mission_id, "mission_no_result", "未产生任何结果")

        return self.get_mission(mission_id)

    def run_module(self, mission_id: str, module_id: str,
                   allow_browser_automation: bool = False) -> Optional[Dict[str, Any]]:
        """执行单个模块 — 通过 ModuleExecutor 分发

        Args:
            mission_id: Mission ID
            module_id: 模块 ID
            allow_browser_automation: 是否允许浏览器自动化采集
        """
        with get_db() as db:
            row = db.execute(
                "SELECT * FROM boss_mission_modules WHERE mission_id = ? AND module_id = ?",
                (mission_id, module_id)
            ).fetchone()
            if not row:
                return None
            module = dict(row)

        # 更新模块状态为 running + started_at
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE boss_mission_modules SET status = 'running', started_at = ?, updated_at = ? WHERE mission_id = ? AND module_id = ?",
                (now, now, mission_id, module_id)
            )
            db.commit()
        self._log_event(mission_id, "module_started", f"开始执行模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)}",
                        module_id=module_id)

        # 获取 mission 信息
        mission = self.get_mission(mission_id)
        goal = mission["goal"] if mission else ""
        template_id = mission.get("template_id", "") if mission else ""

        # 构建 prev_results 上下文（从已完成的模块中收集 structured_output）
        prev_results = {}
        if mission:
            for m in mission.get("modules", []):
                if m["module_id"] != module_id and m.get("structured_output"):
                    prev_results[m["module_id"]] = m

        # 获取模块执行器
        from backend.services.boss_module_executors import get_executor
        executor = get_executor(template_id, module_id)

        start_time = time.time()
        timeout_sec = MODULE_TIMEOUT_SECONDS.get(module_id, MODULE_TIMEOUT_DEFAULT)

        try:
            # Phase 6.16: 在独立线程中执行，带硬超时
            # 不用 with 语句，避免 __exit__(wait=True) 阻塞请求
            import concurrent.futures
            pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
            future = pool.submit(executor.execute, goal, module_id, mission_id, {
                "mission": mission,
                "prev_results": prev_results,
                "allow_browser_automation": allow_browser_automation,
            })
            try:
                exec_result = future.result(timeout=timeout_sec)
            except concurrent.futures.TimeoutError:
                # 超时后立即释放线程池，不等待工作线程结束
                future.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                raise  # 重新抛出，由外层 except 处理状态更新
            except Exception:
                # 其他异常也确保释放
                future.cancel()
                pool.shutdown(wait=False, cancel_futures=True)
                raise
            else:
                # 正常完成，等待线程池清理
                pool.shutdown(wait=True)
            duration_ms = int((time.time() - start_time) * 1000)

            # v2: 模块状态更细腻 — 有结果文本即使执行有瑕疵也保留展示
            # 但 approval-blocked 的模块不视为 partial，保持 failed
            if exec_result.ok:
                status = "done"
            elif exec_result.mode == "blocked":
                status = "failed"
            elif exec_result.final_answer and len(exec_result.final_answer.strip()) >= 10:
                status = "partial"  # 有可读结果但执行有问题
            else:
                status = "failed"

            updated = self._update_module_result(
                mission_id, module_id, status,
                exec_result.final_answer, exec_result.confidence,
                exec_result.warnings, exec_result.error,
                exec_result.used_tools, exec_result.mode,
                exec_result.next_actions, duration_ms,
                exec_result.structured_output,
                expected_status="running",
            )

            if not updated:
                # 状态已不是 running（可能被 timeout/stale cleanup/用户操作改过）
                # 不覆盖现有状态，记录事件，返回当前最新 mission
                current = self.get_mission(mission_id)
                current_mod = next((m for m in (current["modules"] if current else []) if m["module_id"] == module_id), None)
                current_status = current_mod["status"] if current_mod else "unknown"
                self._log_event(mission_id, "module_result_ignored",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 结果被忽略（状态已变为 {current_status}）",
                                module_id=module_id,
                                payload={"module_id": module_id,
                                         "attempted_status": status,
                                         "current_status": current_status,
                                         "reason": "expected_status mismatch — module no longer running"})
                return self.get_mission(mission_id)

            if exec_result.ok:
                self._log_event(mission_id, "module_succeeded",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 执行完成",
                                module_id=module_id,
                                payload={"confidence": exec_result.confidence, "duration_ms": duration_ms, "provider": exec_result.provider})
            else:
                self._log_event(mission_id, "module_failed",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 执行失败: {exec_result.error[:100]}",
                                module_id=module_id,
                                payload={"error": exec_result.error, "duration_ms": duration_ms, "provider": exec_result.provider})

        except concurrent.futures.TimeoutError:
            # Phase 6.16: 模块执行超时 → interrupted
            duration_ms = int((time.time() - start_time) * 1000)
            logger.warning(f"BossCommandCenter: Module {module_id} timed out after {timeout_sec}s")
            # 保留已有 result（底层线程可能已部分写入）
            existing = self.get_mission(mission_id)
            existing_mod = next((m for m in (existing["modules"] if existing else []) if m["module_id"] == module_id), None)
            existing_result = existing_mod.get("result", "") if existing_mod else ""
            updated = self._update_module_result(
                mission_id, module_id, "interrupted",
                existing_result, 0.0,
                [f"模块执行超时（{timeout_sec}s），请人工检查或重跑"],
                f"模块执行超时（{timeout_sec}s），请人工检查或重跑",
                [], "timeout", [], duration_ms, {},
                expected_status="running",
            )
            if not updated:
                current = self.get_mission(mission_id)
                current_mod = next((m for m in (current["modules"] if current else []) if m["module_id"] == module_id), None)
                current_status = current_mod["status"] if current_mod else "unknown"
                self._log_event(mission_id, "module_result_ignored",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 超时标记被忽略（状态已变为 {current_status}）",
                                module_id=module_id,
                                payload={"module_id": module_id,
                                         "attempted_status": "interrupted",
                                         "current_status": current_status,
                                         "reason": "expected_status mismatch — module no longer running"})
                return self.get_mission(mission_id)
            self._log_event(mission_id, "module_timeout",
                            f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 执行超时（{timeout_sec}s）",
                            module_id=module_id,
                            payload={"timeout_sec": timeout_sec, "duration_ms": duration_ms})

        except Exception as e:
            logger.error(f"BossCommandCenter: Module {module_id} failed: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            # v2: 异常时也尽量保留已有结果
            updated = self._update_module_result(
                mission_id, module_id, "failed",
                "", 0.0, [str(e)], str(e), [], "error", [], duration_ms, {},
                expected_status="running",
            )
            if not updated:
                current = self.get_mission(mission_id)
                current_mod = next((m for m in (current["modules"] if current else []) if m["module_id"] == module_id), None)
                current_status = current_mod["status"] if current_mod else "unknown"
                self._log_event(mission_id, "module_result_ignored",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 异常结果被忽略（状态已变为 {current_status}）",
                                module_id=module_id,
                                payload={"module_id": module_id,
                                         "attempted_status": "failed",
                                         "current_status": current_status,
                                         "reason": "expected_status mismatch — module no longer running"})
                return self.get_mission(mission_id)
            self._log_event(mission_id, "module_failed",
                            f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 异常: {str(e)[:100]}",
                            module_id=module_id,
                            payload={"error": str(e), "duration_ms": duration_ms})

        # 更新 Mission 整体状态
        self._update_mission_status_from_modules(mission_id)

        return self.get_mission(mission_id)

    # ── 导出 ──────────────────────────────────────────────

    def export_mission(self, mission_id: str, fmt: str = "json") -> Optional[Dict[str, Any]]:
        """导出 Mission 报告

        Args:
            mission_id: Mission ID
            fmt: "json" 或 "markdown"

        Returns:
            {"content": str, "filename": str, "content_type": str}
        """
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        if fmt == "markdown":
            content = self._export_markdown(mission)
            self._log_event(mission_id, "mission_exported", "导出 Markdown 报告", payload={"format": "markdown"})
            self._log_event(mission_id, "report_generated", f"生成 {fmt.upper()} 报告",
                          payload={"format": fmt, "content_length": len(content)})
            return {
                "content": content,
                "filename": f"boss-mission-{mission_id}.md",
                "content_type": "text/markdown; charset=utf-8",
            }
        else:
            content = json.dumps(mission, ensure_ascii=False, indent=2)
            self._log_event(mission_id, "mission_exported", "导出 JSON 报告", payload={"format": "json"})
            self._log_event(mission_id, "report_generated", f"生成 {fmt.upper()} 报告",
                          payload={"format": fmt, "content_length": len(content)})
            return {
                "content": content,
                "filename": f"boss-mission-{mission_id}.json",
                "content_type": "application/json; charset=utf-8",
            }

    def _export_markdown(self, mission: Dict[str, Any]) -> str:
        """生成 Markdown 格式的老板可读报告"""
        lines = []
        status_text = {
            "pending_review": "待确认执行", "pending": "待执行",
            "running": "执行中", "done": "已完成", "failed": "失败",
            "ready_for_review": "等待审核", "partial": "部分完成",
        }
        mission_status = status_text.get(mission["status"], mission["status"])

        lines.append(f"# 运营指挥台报告")
        lines.append("")
        lines.append(f"**任务目标：** {mission['goal']}")
        lines.append(f"**总体状态：** {mission_status}")
        lines.append(f"**创建时间：** {mission.get('created_at', 'N/A')}")
        lines.append(f"**更新时间：** {mission.get('updated_at', 'N/A')}")
        lines.append("")
        lines.append("---")
        lines.append("")

        # 各模块结果
        for mod in mission.get("modules", []):
            mod_status = status_text.get(mod["status"], mod["status"])
            lines.append(f"## {mod['title']}（{mod_status}）")
            lines.append("")

            if mod["status"] == "skipped":
                lines.append("*此模块未启用。*")
                lines.append("")
                continue

            if mod.get("result"):
                lines.append(mod["result"])
                lines.append("")

            # 元信息
            if mod.get("confidence", 0) > 0:
                lines.append(f"- **置信度：** {mod['confidence']:.0%}")
            if mod.get("duration_ms", 0) > 0:
                lines.append(f"- **耗时：** {mod['duration_ms']}ms")
            if mod.get("used_tools"):
                lines.append(f"- **使用工具：** {', '.join(mod['used_tools'])}")
            if mod.get("mode"):
                lines.append(f"- **执行模式：** {mod['mode']}")

            # Warnings
            if mod.get("warnings"):
                lines.append("")
                lines.append("**注意事项：**")
                for w in mod["warnings"]:
                    lines.append(f"- ⚠️ {w}")

            # Next actions
            if mod.get("next_actions"):
                lines.append("")
                lines.append("**下一步建议：**")
                for action in mod["next_actions"]:
                    lines.append(f"- {action}")

            # Error
            if mod.get("error"):
                lines.append("")
                lines.append(f"**错误：** {mod['error']}")

            lines.append("")
            lines.append("---")
            lines.append("")

        lines.append(f"*报告生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")
        return "\n".join(lines)

    # ── 内部方法 ──────────────────────────────────────────

    def _update_mission_status(self, mission_id: str, status: str):
        """更新 Mission 状态"""
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE boss_missions SET status = ?, updated_at = ? WHERE mission_id = ?",
                (status, now, mission_id)
            )
            db.commit()

    def _update_module_status(self, mission_id: str, module_id: str, status: str):
        """更新模块状态"""
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute(
                "UPDATE boss_mission_modules SET status = ?, updated_at = ? WHERE mission_id = ? AND module_id = ?",
                (status, now, mission_id, module_id)
            )
            db.commit()

    def _update_module_result(
        self, mission_id: str, module_id: str, status: str,
        result: str, confidence: float, warnings: List[str],
        error: str, used_tools: List[str], mode: str,
        next_actions: List[str] = None, duration_ms: int = 0,
        structured_output: Dict[str, Any] = None,
        expected_status: str | None = None
    ) -> bool:
        """更新模块执行结果

        Args:
            expected_status: 如果传入，UPDATE 语句会加 WHERE status = ? 条件，
                只在模块当前状态匹配时才写入。返回 False 表示未更新（状态已变化）。
                不传则保持原有无条件更新，用于非竞态场景（如 timeout 首次写入）。

        Returns:
            True: 成功更新
            False: 未更新（expected_status 不匹配，说明状态已被其他路径修改）
        """
        now = datetime.now().isoformat()
        with get_db() as db:
            if expected_status is not None:
                cursor = db.execute(
                    """UPDATE boss_mission_modules
                       SET status = ?, result = ?, confidence = ?,
                           warnings = ?, error = ?, used_tools = ?,
                           mode = ?, next_actions = ?, structured_output = ?,
                           finished_at = ?, duration_ms = ?, updated_at = ?
                       WHERE mission_id = ? AND module_id = ? AND status = ?""",
                    (
                        status, result, confidence,
                        json.dumps(warnings, ensure_ascii=False), error,
                        json.dumps(used_tools, ensure_ascii=False),
                        mode, json.dumps(next_actions or [], ensure_ascii=False),
                        json.dumps(structured_output or {}, ensure_ascii=False),
                        now, duration_ms, now, mission_id, module_id, expected_status
                    )
                )
                db.commit()
                return cursor.rowcount > 0
            else:
                db.execute(
                    """UPDATE boss_mission_modules
                       SET status = ?, result = ?, confidence = ?,
                           warnings = ?, error = ?, used_tools = ?,
                           mode = ?, next_actions = ?, structured_output = ?,
                           finished_at = ?, duration_ms = ?, updated_at = ?
                       WHERE mission_id = ? AND module_id = ?""",
                    (
                        status, result, confidence,
                        json.dumps(warnings, ensure_ascii=False), error,
                        json.dumps(used_tools, ensure_ascii=False),
                        mode, json.dumps(next_actions or [], ensure_ascii=False),
                        json.dumps(structured_output or {}, ensure_ascii=False),
                        now, duration_ms, now, mission_id, module_id
                    )
                )
                db.commit()
                return True


# 全局实例
_service = None


def get_boss_command_center() -> BossCommandCenterService:
    """获取 BossCommandCenter 单例"""
    global _service
    if _service is None:
        _service = BossCommandCenterService()
    return _service
