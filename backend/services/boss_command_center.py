"""
Boss Command Center Service — 老板运营指挥台业务引擎

职责：
1. 创建 Mission（5 个模块，支持 enabled_modules 选择性执行）
2. 执行单个模块 / 整个 Mission
3. 持久化 Mission 结果（含进度字段 started_at/finished_at/duration_ms）
4. 查询 Mission 历史
5. 导出 Mission 报告（JSON / Markdown）
6. 事件日志（mission_created/started/succeeded/failed, module_*, exported）
"""
import uuid
import json
import time
from datetime import datetime
from typing import Dict, Any, List, Optional
from backend.database.database import get_db
from backend.logger import get_logger

logger = get_logger()

# ── 模块定义 ────────────────────────────────────────────
MODULE_DEFINITIONS = {
    "strategy": {
        "title": "战略摘要",
        "description": "把老板目标压缩成业务判断、关键机会和风险。",
        "prompt_template": (
            "请作为公司运营顾问，围绕这个业务目标输出一份战略摘要：{goal}。"
            "要求包含目标解读、核心机会、主要风险、优先级建议。"
        ),
    },
    "market": {
        "title": "市场与竞品",
        "description": "调研市场、用户、竞品和可进入机会。",
        "prompt_template": (
            "请调研这个业务目标相关的市场和竞品：{goal}。"
            "要求包含市场趋势、目标用户、竞品对比、差异化机会，并尽量给出来源。"
        ),
    },
    "marketing": {
        "title": "营销方案",
        "description": "生成卖点、内容方向、渠道打法和首批文案。",
        "prompt_template": (
            "请为这个业务目标制定营销方案：{goal}。"
            "要求包含目标用户、核心卖点、渠道策略、内容选题、3 条可直接使用的推广文案。"
        ),
    },
    "landing": {
        "title": "落地页草稿",
        "description": "生成首屏、卖点、证明、CTA 等落地页结构。",
        "prompt_template": (
            "请为这个业务目标生成一个落地页草稿：{goal}。"
            "要求包含 H1、首屏副标题、3-5 个卖点区块、信任证明、CTA 文案和页面结构说明。"
        ),
    },
    "actions": {
        "title": "执行清单",
        "description": "拆成今天、本周、本月能执行的行动项。",
        "prompt_template": (
            "请把这个业务目标拆成可执行清单：{goal}。"
            "要求按今天、本周、本月分组，给出任务、负责人角色、优先级、验收标准。"
        ),
    },
}

MODULE_ORDER = ["strategy", "market", "marketing", "landing", "actions"]


def _init_boss_tables():
    """建表（幂等）— 含进度字段"""
    with get_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS boss_missions (
                mission_id TEXT PRIMARY KEY,
                goal TEXT NOT NULL,
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
                started_at TEXT,
                finished_at TEXT,
                duration_ms INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                updated_at TEXT DEFAULT (datetime('now','localtime')),
                FOREIGN KEY (mission_id) REFERENCES boss_missions(mission_id)
            )
        """)
        # 尝试添加新列（已存在的表不会报错）
        for col in ("next_actions TEXT DEFAULT '[]'", "started_at TEXT", "finished_at TEXT", "duration_ms INTEGER DEFAULT 0"):
            try:
                db.execute(f"ALTER TABLE boss_mission_modules ADD COLUMN {col}")
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

    # ── Mission CRUD ──────────────────────────────────────

    def create_mission(self, goal: str, auto_run: bool = False, enabled_modules: List[str] = None) -> Dict[str, Any]:
        """创建 Mission

        Args:
            goal: 业务目标
            auto_run: 创建后是否立即执行
            enabled_modules: 启用的模块 ID 列表，None 表示全部启用
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
                "INSERT INTO boss_missions (mission_id, goal, status, created_at, updated_at) VALUES (?, ?, 'pending', ?, ?)",
                (mission_id, goal, now, now)
            )
            for module_id in MODULE_ORDER:
                definition = MODULE_DEFINITIONS[module_id]
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
                        payload={"enabled_modules": active_modules})
        for module_id in MODULE_ORDER:
            if module_id not in active_modules:
                self._log_event(mission_id, "module_skipped", f"模块 {MODULE_DEFINITIONS[module_id]['title']} 已跳过（未启用）",
                                module_id=module_id)
        mission = self.get_mission(mission_id)

        if auto_run:
            mission = self.run_mission(mission_id)

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
                mission["modules"].append(mod)

            return mission

    # ── 执行 ──────────────────────────────────────────────

    def run_mission(self, mission_id: str) -> Optional[Dict[str, Any]]:
        """执行整个 Mission（顺序执行，跳过 skipped 模块）"""
        mission = self.get_mission(mission_id)
        if not mission:
            return None

        self._update_mission_status(mission_id, "running")
        self._log_event(mission_id, "mission_started", "开始执行任务")

        for module in mission["modules"]:
            # 跳过已完成或已跳过的模块
            if module["status"] in ("done", "skipped"):
                continue
            self.run_module(mission_id, module["module_id"])

        # 重新读取并计算最终状态
        mission = self.get_mission(mission_id)
        active_modules = [m for m in mission["modules"] if m["status"] != "skipped"]
        all_done = all(m["status"] == "done" for m in active_modules) if active_modules else True
        any_failed = any(m["status"] == "failed" for m in active_modules)

        if any_failed:
            self._update_mission_status(mission_id, "failed")
            self._log_event(mission_id, "mission_failed", "任务执行失败（部分模块失败）")
        else:
            self._update_mission_status(mission_id, "done")
            self._log_event(mission_id, "mission_succeeded", "任务执行完成")

        return self.get_mission(mission_id)

    def run_module(self, mission_id: str, module_id: str) -> Optional[Dict[str, Any]]:
        """执行单个模块"""
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

        prompt = module["prompt"]
        goal = ""
        mission = self.get_mission(mission_id)
        if mission:
            goal = mission["goal"]

        # 使用 LocalAgentRuntime 执行
        runtime = self._get_runtime()
        start_time = time.time()

        try:
            result = runtime.execute(prompt, {
                "boss_mission": True,
                "mission_id": mission_id,
                "mission_module": module_id,
                "mission_goal": goal,
            })
            duration_ms = int((time.time() - start_time) * 1000)

            # 提取结果
            ok = result.get("ok", False)
            final_answer = result.get("final_answer", "")
            confidence = result.get("confidence", 0.0)
            warnings = result.get("warnings", [])
            used_tools = result.get("used_tools", [])
            mode = result.get("mode", "local")
            error = result.get("error", "")
            next_actions = result.get("next_actions", [])

            # 特殊处理：market 模块无联网能力时加 warning
            if module_id == "market":
                if "mimo" not in used_tools and not result.get("used_web_search"):
                    warnings.append("市场模块未联网，结果基于模型已有知识，可能不够最新")

            # actions 模块必须有可执行清单
            if module_id == "actions" and final_answer:
                if not any(kw in final_answer for kw in ["今天", "本周", "本月", "Today", "This week"]):
                    warnings.append("执行清单未按今天/本周/本月分组，建议重新生成")

            # 更新数据库
            status = "done" if ok else "failed"
            self._update_module_result(
                mission_id, module_id, status,
                final_answer, confidence, warnings, error,
                used_tools, mode, next_actions, duration_ms
            )

            if ok:
                self._log_event(mission_id, "module_succeeded",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 执行完成",
                                module_id=module_id,
                                payload={"confidence": confidence, "duration_ms": duration_ms})
            else:
                self._log_event(mission_id, "module_failed",
                                f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 执行失败: {error[:100]}",
                                module_id=module_id,
                                payload={"error": error, "duration_ms": duration_ms})

            return self.get_mission(mission_id)

        except Exception as e:
            logger.error(f"BossCommandCenter: Module {module_id} failed: {e}")
            duration_ms = int((time.time() - start_time) * 1000)
            self._update_module_result(
                mission_id, module_id, "failed",
                "", 0.0, [], str(e), [], "error", [], duration_ms
            )
            self._log_event(mission_id, "module_failed",
                            f"模块 {MODULE_DEFINITIONS.get(module_id, {}).get('title', module_id)} 异常: {str(e)[:100]}",
                            module_id=module_id,
                            payload={"error": str(e), "duration_ms": duration_ms})
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
            return {
                "content": content,
                "filename": f"boss-mission-{mission_id}.md",
                "content_type": "text/markdown; charset=utf-8",
            }
        else:
            content = json.dumps(mission, ensure_ascii=False, indent=2)
            self._log_event(mission_id, "mission_exported", "导出 JSON 报告", payload={"format": "json"})
            return {
                "content": content,
                "filename": f"boss-mission-{mission_id}.json",
                "content_type": "application/json; charset=utf-8",
            }

    def _export_markdown(self, mission: Dict[str, Any]) -> str:
        """生成 Markdown 格式的老板可读报告"""
        lines = []
        status_text = {"pending": "待执行", "running": "执行中", "done": "已完成", "failed": "失败"}
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
        next_actions: List[str] = None, duration_ms: int = 0
    ):
        """更新模块执行结果"""
        now = datetime.now().isoformat()
        with get_db() as db:
            db.execute(
                """UPDATE boss_mission_modules
                   SET status = ?, result = ?, confidence = ?,
                       warnings = ?, error = ?, used_tools = ?,
                       mode = ?, next_actions = ?,
                       finished_at = ?, duration_ms = ?, updated_at = ?
                   WHERE mission_id = ? AND module_id = ?""",
                (
                    status, result, confidence,
                    json.dumps(warnings, ensure_ascii=False), error,
                    json.dumps(used_tools, ensure_ascii=False),
                    mode, json.dumps(next_actions or [], ensure_ascii=False),
                    now, duration_ms, now, mission_id, module_id
                )
            )
            db.commit()


# 全局实例
_service = None


def get_boss_command_center() -> BossCommandCenterService:
    """获取 BossCommandCenter 单例"""
    global _service
    if _service is None:
        _service = BossCommandCenterService()
    return _service
