"""Commander Agent — 多智能体协作主脑（集成技能和记忆系统）"""

import json
import os
import traceback
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.database.database import SessionDB, StepDB, TaskDB
from backend.config import get_ai_config, AI_PROVIDER, get_brain_manager
from backend.services.usage_stats import record_usage
from backend.services.agent_loader import load_agent, load_agent_instance
from backend.ai_registry.registry import get_registry
from core.skills.skill_manager import get_skill_manager
from core.memory.memory_store import get_memory_store
from backend.logger import get_logger

_cmd_logger = get_logger()


# ── Agent 懒加载 ──────────────────────────────────────────

_agent_cache: Dict[str, Any] = {}

def _get_agent(name: str, **kwargs):
    """延迟加载 agent"""
    cache_key = f"{name}_{kwargs}"
    if cache_key not in _agent_cache:
        agent_map = {
            "ceo": ("agents.ceo_agent.agent", "CEOAgent"),
            "codex": ("agents.codex_agent.agent", "CodexAgent"),
            "qa": ("agents.qa_agent.agent", "QAAgent"),
            "cto": ("agents.cto_agent.agent", "CTOAgent"),
            "system": ("agents.system_agent.agent", "SystemAgent"),
            "openclaw": ("agents.openclaw_agent.agent", "OpenClawAgent"),
            "image": ("agents.image_agent.agent", "ImageAgent"),
            "marketing": ("agents.marketing_agent.agent", "MarketingAgent"),
            "video": ("agents.video_agent.agent", "VideoAgent"),
            "data": ("agents.data_agent.agent", "DataAgent"),
        }
        if name in agent_map:
            entrypoint, class_name = agent_map[name]
            _agent_cache[cache_key] = load_agent_instance(entrypoint, class_name, **kwargs)
        else:
            _agent_cache[cache_key] = None
    return _agent_cache[cache_key]


# ── AI 客户端（新版本使用 Brain Manager）──────────────────────

def _call_ai_v2(prompt: str, system: str = "", temperature: float = 0.3) -> str:
    """调用 AI（使用 Brain Manager 自动选择最佳主脑）"""
    brain_mgr = get_brain_manager()
    result = brain_mgr.chat(
        message=prompt,
        system=system or "你是 AI Company OS 的指挥官。负责拆解目标、调度智能体、生成报告。",
        temperature=temperature,
        max_tokens=4000,
    )

    if result.get("ok"):
        return result.get("reply", "")
    else:
        # 降级到旧版本
        return _call_ai_legacy(prompt, system, temperature)


# ── AI 客户端（旧版本，保持向后兼容）──────────────────────────

# 共享 AI 客户端（连接复用，避免每次调用都 TLS 握手）
import httpx as _httpx
_ai_client: Optional[_httpx.Client] = None
_ai_client_key: tuple = ()  # (provider, api_key) — 变化时重建


def _get_ai_client() -> _httpx.Client:
    """获取或创建共享的 AI HTTP 客户端（连接复用）"""
    global _ai_client, _ai_client_key
    config = get_ai_config()
    current_key = (AI_PROVIDER, config["api_key"][:8] if config["api_key"] else "")

    if _ai_client is None or _ai_client_key != current_key:
        if _ai_client:
            _ai_client.close()
        _ai_client = _httpx.Client(timeout=_httpx.Timeout(60), proxy=None, trust_env=False,
                                   limits=_httpx.Limits(max_keepalive_connections=5))
        _ai_client_key = current_key

    return _ai_client


def _call_ai_legacy(prompt: str, system: str = "", temperature: float = 0.3) -> str:
    """调用 AI API（旧版本，保持向后兼容）"""
    config = get_ai_config()
    api_key = config["api_key"]
    base_url = config["base_url"]
    model = config["model"]

    import time as _time
    client = _get_ai_client()
    start = _time.time()

    # 构建请求 URL
    if AI_PROVIDER == "claude":
        url = f"{base_url}/v1/messages"
        headers = {
            "x-api-key": api_key,
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
        }
        body = {
            "model": model,
            "max_tokens": 4000,
            "system": system or "你是 AI Company OS 的指挥官。",
            "messages": [{"role": "user", "content": prompt}],
        }
    else:
        # DeepSeek / OpenAI 兼容格式
        url = f"{base_url}/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
        body = {
            "model": model,
            "messages": [
                {"role": "system", "content": system or "你是 AI Company OS 的指挥官。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": temperature,
            "max_tokens": 4000,
        }

    try:
        resp = client.post(url, headers=headers, json=body)
        resp.raise_for_status()
        data = resp.json()
        duration_ms = int((_time.time() - start) * 1000)

        # 提取 token 使用量
        prompt_tokens = 0
        completion_tokens = 0
        if AI_PROVIDER == "claude":
            prompt_tokens = data.get("usage", {}).get("input_tokens", 0)
            completion_tokens = data.get("usage", {}).get("output_tokens", 0)
            result = data["content"][0]["text"].strip()
        else:
            prompt_tokens = data.get("usage", {}).get("prompt_tokens", 0)
            completion_tokens = data.get("usage", {}).get("completion_tokens", 0)
            result = data["choices"][0]["message"]["content"].strip()

        # 记录使用量
        record_usage(
            provider=AI_PROVIDER,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            source="commander",
            duration_ms=duration_ms,
            success=True,
        )
        return result
    except Exception as e:
        duration_ms = int((_time.time() - start) * 1000)
        record_usage(
            provider=AI_PROVIDER,
            model=model,
            source="commander",
            duration_ms=duration_ms,
            success=False,
        )
        raise


UNIFIED_SYSTEM_PROMPT = """你是 AI Company OS 的指挥官。你可以: 拆解目标为JSON步骤、评估结果做决策(continue/retry/adjust/ask/complete)、生成中文摘要。

可调度资源: codex(代码执行), openclaw(浏览器截图/抓取), system(系统命令/文件), qa(验收评分), ceo(拆解), cto(技术审查), image(AI图片), marketing(营销文案/SEO), video(视频脚本)

外部AI: cc-switch(DeepSeek通用推理), kimi(长文档分析), chatgpt(对话+图片)

Agent分配规则: codex→代码任务, openclaw→需URL的网页任务, system→命令行/文件操作, cto→代码审查/架构, marketing→文案/SEO, image→图片, video→视频脚本, qa→验收, cc-switch→通用分析/翻译/创作, kimi→长文档/深度阅读, chatgpt→对话/图片

⚠️ 依赖声明规则（v1.5.1 新增）:
- 如果一个步骤需要另一个步骤的输出，必须在 details 中声明 depends_on_step（步骤编号）。
- 例如: "分析竞品数据" 依赖 "抓取竞品网页" → depends_on_step: 1
- 无依赖的步骤不用声明。
- 有依赖的步骤会在前置步骤完成后才执行，并自动注入前置步骤的输出。

输出格式: 拆解时只输出JSON数组[{step,description,agent,task_type,details:{depends_on_step?}}], 决策时输出{decision,reason}, 摘要时输出中文文本。"""


def _topological_sort_steps(steps: List[Dict]) -> List[Dict]:
    """拓扑排序：将有 depends_on_step 声明的步骤排到其依赖之后。
    
    例如：步骤 2 的 details.depends_on_step = 1 → 步骤 2 一定在步骤 1 之后执行。
    无依赖声明的步骤保持原序。
    如果有循环依赖，降级为原序（不崩溃）。
    """
    if not steps:
        return steps
    
    # 分离有依赖和无依赖的步骤
    independent = []
    dependent_map: Dict[int, Dict] = {}  # step_number → step
    
    for s in steps:
        details = s.get("details", {})
        if isinstance(details, dict) and details.get("depends_on_step"):
            dependent_map[s["step"]] = s
        else:
            independent.append(s)
    
    if not dependent_map:
        return steps  # 没有依赖声明，保持原序
    
    # 构建结果列表：无依赖步骤在前，有依赖步骤插入到其依赖之后
    result = list(independent)  # 复制无依赖步骤
    
    # 按 depends_on_step 排序有依赖步骤
    sorted_deps = sorted(dependent_map.items(), key=lambda x: x[0])
    
    for step_num, step in sorted_deps:
        details = step.get("details", {})
        if not isinstance(details, dict):
            result.append(step)
            continue
        target = details.get("depends_on_step")
        # 找到结果列表中 depends_on_step 的位置
        insert_idx = len(result)  # 默认放在末尾
        for idx, existing in enumerate(result):
            if existing["step"] == target:
                insert_idx = idx + 1
                break
        result.insert(insert_idx, step)
    
    return result


class CommanderAgent:
    """指挥官主脑"""

    def __init__(self, progress_callback=None):
        """
        Args:
            progress_callback: 可选的回调函数，用于异步推送执行进度
                             签名: progress_callback(data: dict)
                             数据格式: {"type": "step_done"|"summary", ...}
        """
        self.progress_callback = progress_callback

        # v1.5.1: CEO 反问暂存
        self.pending_clarifying_questions: List[str] = []

        # 实例化所有内置 Agent（使用延迟加载）
        self._agents = {}
        agent_names = ["ceo", "codex", "qa", "cto", "openclaw", "system", "image", "marketing", "video", "data"]
        for name in agent_names:
            agent = _get_agent(name)
            if agent is not None:
                self._agents[agent.AGENT_ID] = agent
            else:
                _cmd_logger.warning(f"[Commander] Agent '{name}' unavailable")

        # 加载用户插件
        try:
            from agents.user_plugins.adapter import discover_plugins
            for plugin in discover_plugins():
                self._agents[plugin.AGENT_ID] = plugin
        except Exception as e:
            _cmd_logger.warning(f"[Commander] 加载用户插件失败: {e}")

        # 向后兼容：保留常用引用
        self.ceo = self._agents.get("ceo")
        self.codex = self._agents.get("codex")
        self.qa = self._agents.get("qa")
        self.openclaw = self._agents.get("openclaw")
        self.system = self._agents.get("system")

    def _get_executor(self, agent: str):
        """通过 AGENT_ID 查找 Agent 实例"""
        return self._agents.get(agent)

    # ═══════════════════════════════════════════════════════════
    # 1. 拆解目标 → 步骤列表
    # ═══════════════════════════════════════════════════════════

    def _steps_to_sqlite(self, session_id: str, steps: List[Dict]):
        """将步骤列表写入 SQLite"""
        SessionDB.update(session_id, total_steps=len(steps))
        for s in steps:
            step_details = dict(s.get("details", {}))
            if not step_details:
                step_details = {k: v for k, v in s.items() if k in ("url", "code", "files", "selector", "command", "mode", "extract")}
            StepDB.create(
                session_id=session_id,
                step_number=s["step"],
                description=s.get("description", ""),
                assigned_agent=s.get("agent", ""),
                details=step_details,
            )

    def _ceo_decompose(self, goal: str, session_id: str) -> Optional[List[Dict]]:
        """通过 CEO Agent 拆解（带完整的 URL/details 等结构化字段，带超时围栏）"""
        ceo_timeout = int(os.getenv("CEO_TIMEOUT", "20"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(self.ceo.run, {"task_id": f"{session_id}_decompose", "goal": goal})
            try:
                ceo_result = future.result(timeout=ceo_timeout)
            except TimeoutError:
                _cmd_logger.warning(f"[Commander] CEO Agent 拆解超时 ({ceo_timeout}s)，降级到 AI 直拆")
                return None
            except Exception as e:
                _cmd_logger.error(f"[Commander] CEO Agent 拆解异常: {e}")
                return None

        # v1.5.1: 检查 CEO 是否需要反问用户
        ceo_data = ceo_result.get("data", ceo_result.get("output", {}))
        clarifying = ceo_data.get("clarifying_questions", [])
        if clarifying:
            _cmd_logger.info(f"[Commander] CEO 需要反问用户: {clarifying}")
            self.pending_clarifying_questions = clarifying
            return []  # 空列表但不是 None，标记为"有结果但不是步骤"

        tasks = ceo_result.get("output", {}).get("created_tasks", [])
        if not tasks:
            return None
        # 动态构建 agent 名称映射（支持旧名称 → AGENT_ID）
        agent_map = {}
        for agent_id, agent in self._agents.items():
            agent_map[agent_id] = agent_id
            # 兼容旧名称格式（如 "codex_agent" → "codex"）
            if not agent_id.startswith("plugin:"):
                agent_map[f"{agent_id}_agent"] = agent_id
        # 外部服务（非本地 Agent）
        agent_map.update({"cc-switch": "cc-switch", "kimi": "kimi", "chatgpt": "chatgpt"})
        steps = []
        for i, t in enumerate(tasks, 1):
            steps.append({
                "step": i, "description": t.get("goal", f"步骤 {i}"),
                "agent": agent_map.get(t.get("assigned_to", ""), "qa"),
                "task_type": t.get("task_type", "qa_review"),
                "details": t,
            })
        return steps

    def _ai_decompose(self, goal: str, session_id: str) -> Optional[List[Dict]]:
        """降级：直接调用 AI API 拆解"""
        try:
            raw = _call_ai_v2(f"【拆解模式】将以下目标拆解为JSON步骤数组:\n{goal}", system=UNIFIED_SYSTEM_PROMPT)
            raw_steps = json.loads(raw)
            if not isinstance(raw_steps, list):
                raise ValueError("AI 未返回数组")
            steps = []
            for s in raw_steps:
                details = dict(s.get("details", {}))
                if not details:
                    details = {k: v for k, v in s.items() if k in ("url", "code", "files", "selector", "command", "mode", "extract")}
                steps.append({
                    "step": s["step"],
                    "description": s.get("description", f"步骤 {s['step']}"),
                    "agent": s.get("agent", "qa"),
                    "task_type": s.get("task_type", "qa_review"),
                    "details": details,
                })
            return steps
        except Exception as e:
            _cmd_logger.error(f"[Commander] 直接 AI 调用失败: {e}")
            return None

    def decompose_goal(self, goal: str, session_id: str) -> List[Dict]:
        """将目标拆解为步骤 — 缓存+技能上下文+记忆"""
        # 拆解缓存（相同goal跳过LLM调用）
        from core.cache_store import cache
        import hashlib
        ck = f"decomp:{hashlib.md5(goal.strip().lower().encode()).hexdigest()[:16]}"
        cached = cache.get(ck)
        if cached:
            self._steps_to_sqlite(session_id, cached)
            return cached

        # 获取相关技能上下文
        skill_mgr = get_skill_manager()
        skill_context = skill_mgr.get_context_for_goal(goal)

        # 获取相关记忆
        memory = get_memory_store()
        memory_context = memory.get_context(goal)

        # 增强的拆解（带技能+记忆）
        self.pending_clarifying_questions = []
        steps = self._ceo_decompose(goal, session_id)

        # v1.5.1: CEO 反问 → 直接返回给用户
        if self.pending_clarifying_questions:
            questions = self.pending_clarifying_questions
            self.pending_clarifying_questions = []
            # 返回一个特殊的"步骤"让 UI 层知道需要反问
            return [{
                "step": 0,
                "description": "目标需要澄清",
                "agent": "ceo",
                "task_type": "clarify",
                "details": {
                    "clarifying_questions": questions,
                    "goal": goal,
                },
                "ai_answer": f"你的目标「{goal}」不够清晰，我需要确认以下问题后才能拆解：\n\n" +
                            "\n".join(f"• {q}" for q in questions) +
                            "\n\n请补充信息后重新提交。",
            }]

        if not steps:
            steps = self._ai_decompose(goal, session_id)
        if not steps:
            # 兜底：直接调 AI 回答
            try:
                ai_reply = _call_ai_v2(prompt=f"【对话模式】请用中文回答:\n{goal}", temperature=0.7, system=UNIFIED_SYSTEM_PROMPT)
            except Exception as e:
                _cmd_logger.error(f"[Commander] 兜底 AI 调用失败: {e}")
                ai_reply = f"抱歉，我暂时无法回答这个问题。系统提示：{str(e)[:200]}"
            steps = [{"step": 1, "description": goal, "agent": "cc-switch",
                      "task_type": "chat", "details": {"goal": goal},
                      "ai_answer": ai_reply}]
        self._steps_to_sqlite(session_id, steps)
        cache.set(ck, steps, ttl=300)  # Cache decomposition for 5 minutes
        return steps

    # ═══════════════════════════════════════════════════════════
    # 2. 执行所有步骤（自动循环）
    # ═══════════════════════════════════════════════════════════

    def execute_session(self, session_id: str) -> Dict[str, Any]:
        """全自动执行一个 session 的所有步骤"""
        session = SessionDB.get(session_id)
        if not session:
            return {"status": "error", "message": "Session 不存在"}

        all_steps = StepDB.list_by_session(session_id)
        # v1.5.1: 拓扑排序——有 depends_on_step 的步骤排到其依赖之后
        all_steps = _topological_sort_steps(all_steps)
        results = []
        retry_counts: Dict[int, int] = {}

        previous_results = {}  # 保存各步骤的执行结果，供后续步骤（如QA）使用

        # 检查是否有兜底的 AI 回答（不需要执行）
        fallback_step = None
        for step in all_steps:
            details = step.get("details", {})
            if isinstance(details, dict) and details.get("ai_answer"):
                fallback_step = (step, details["ai_answer"])
                break

        if fallback_step:
            step, ai_answer = fallback_step
            StepDB.update(session_id, step["step_number"], status="completed", result_summary=ai_answer[:200])
            SessionDB.update(session_id, status="completed", summary=ai_answer,
                             completed_steps=1, completed_at=datetime.now().isoformat())
            if self.progress_callback:
                self.progress_callback({"type": "summary", "summary": ai_answer, "results": []})
            return {"status": "completed", "session_id": session_id, "summary": ai_answer, "results": []}

        for step in all_steps:
            step_num = step["step_number"]
            step_agent = step.get("assigned_agent", "")
            if step["status"] == "completed":
                results.append({"step": step_num, "status": "已完成", "result": step.get("result_summary")})
                continue

            # 进度回调：步骤开始
            if self.progress_callback:
                self.progress_callback({
                    "type": "step_start",
                    "step": step_num,
                    "total_steps": len(all_steps),
                    "agent": step_agent,
                    "description": step.get("description", ""),
                })

            # 执行（含异常兜底 — _execute_step 内部异常不会导致整个 session 崩溃）
            retry_counts.setdefault(step_num, 0)
            while retry_counts[step_num] <= 2:
                try:
                    result = self._execute_step(session_id, step_num, step, previous_results)
                except Exception as e:
                    import traceback
                    tb = traceback.format_exc()
                    result = {
                        "step": step_num, "status": "失败",
                        "result": f"步骤执行异常: {str(e)[:200]}",
                        "agent": step_agent, "error": tb[-500:],
                    }
                    StepDB.update(session_id, step_num, status="failed",
                                  result_summary=str(e)[:200])
                    # 异常发生后不再重试该步骤
                    results.append(result)
                    break
                results.append(result)

                # 进度回调：每完成一步就推送
                if self.progress_callback:
                    self.progress_callback({
                        "type": "step_done",
                        "step": step_num,
                        "total_steps": len(all_steps),
                        "agent": step_agent,
                        "status": result.get("status"),
                        "description": step.get("description", ""),
                        "result": str(result.get("result", ""))[:200],
                    })

                # 保存执行结果供后续步骤引用
                if step_agent != "qa":
                    previous_results[step_num] = result.get("result", {}) if isinstance(result.get("result"), dict) else {"text": str(result.get("result", ""))}
                    # 也存一份 data 字段（OpenClaw 返回的抓取数据）
                    data = result.get("result", {}).get("data", []) if isinstance(result.get("result"), dict) else []
                    if data:
                        previous_results[step_num]["data"] = data

                # AI 决策
                remaining = len(all_steps) - step_num
                decision = self._make_decision(
                    step=step, result=result, retry_count=retry_counts[step_num],
                    remaining_steps=remaining,
                )

                StepDB.update(session_id, step_num,
                    status="completed" if decision["decision"] in ("continue", "complete") else "retry",
                    result_summary=str(result.get("result", ""))[:200],
                    decision=decision["decision"],
                    decision_detail=decision.get("reason", ""),
                )

                if decision["decision"] == "continue":
                    break
                elif decision["decision"] == "complete":
                    break
                elif decision["decision"] == "retry":
                    # ✅ FIX v1.5.1: 不再自动重试（死循环根因）。
                    # QA 说"不及格"≠系统知道"怎么及格"——没有新信息输入的重试毫无意义。
                    # 改为标记为"需复查"，跳过当前步骤，让用户看到后再决定。
                    _cmd_logger.warning(
                        f"[Commander] 步骤 {step_num} QA 判定需重试，跳过自动重试，标记为需人工复查"
                    )
                    result["status"] = "需复查"
                    result["_auto_retry_blocked"] = True
                    result["_retry_reason"] = decision.get("reason", "")
                    StepDB.update(session_id, step_num,
                        status="needs_review",
                        result_summary=str(result.get("result", ""))[:200],
                        decision="retry_blocked",
                        decision_detail=decision.get("reason", "质量不达标，需人工复查"),
                    )
                    break
                elif decision["decision"] == "ask":
                    # 如果有用户输入（continue_session），跳过ask
                    if getattr(self, '_pending_user_input', None):
                        decision = {"decision": "continue", "reason": "用户已回应，自动继续"}
                        # 继续走下面的 continue/break 逻辑
                    else:
                        SessionDB.update(session_id, status="awaiting_user")
                        return {
                            "status": "awaiting_user",
                            "session_id": session_id,
                            "step": step_num,
                            "question": decision.get("message_to_user", "请指示"),
                            "results": results,
                        }
                elif decision["decision"] == "adjust":
                    # ✅ FIX v1.5.1: 同 retry，不再自动重试
                    _cmd_logger.warning(
                        f"[Commander] 步骤 {step_num} AI 建议调整，跳过自动重试，标记为需人工复查"
                    )
                    result["status"] = "需复查"
                    result["_auto_retry_blocked"] = True
                    result["_adjust_reason"] = decision.get("reason", "")
                    StepDB.update(session_id, step_num,
                        status="needs_review",
                        result_summary=str(result.get("result", ""))[:200],
                        decision="adjust_blocked",
                        decision_detail=decision.get("reason", "AI 建议调整，需人工复查"),
                    )
                    break
                else:
                    break

            # 更新 session 进度
            SessionDB.update(session_id, completed_steps=step_num)

        # 全部完成 — 从 session 读取 goal 传给总结函数
        session = SessionDB.get(session_id)
        goal = session.get("goal", "") if session else ""
        summary = self._generate_summary(session_id, results, goal)
        SessionDB.update(session_id, status="completed", summary=summary, completed_at=datetime.now().isoformat())

        # 记录到记忆系统
        memory = get_memory_store()
        memory.remember_result(goal=goal, result={"status": "completed", "results": results},
                               summary=summary, agent="commander")

        # 从执行中学习（创建新技能）
        try:
            skill_mgr = get_skill_manager()
            skill_mgr.learn_from_result(goal=goal, result={"status": "completed", "results": results},
                                        summary=summary)
        except Exception as _learn_err:
            _cmd_logger.warning(f"[Commander] 技能学习失败（不影响主流程）: {_learn_err}")

        # 进度回调：最终总结
        if self.progress_callback:
            self.progress_callback({
                "type": "summary",
                "summary": summary,
                "results": results,
            })

        return {"status": "completed", "session_id": session_id, "summary": summary, "results": results}

    def continue_session(self, session_id: str, user_input: str = "") -> Dict[str, Any]:
        """用户回应后继续执行"""
        session = SessionDB.get(session_id)
        if not session:
            return {"status": "error", "message": "Session 不存在"}
        if session["status"] != "awaiting_user":
            return {"status": "error", "message": "Session 不在等待用户状态"}

        SessionDB.update(session_id, status="active",
                         summary=f"[用户回应] {user_input[:500]}")
        self._pending_user_input = user_input
        result = self.execute_session(session_id)
        # 清理
        if hasattr(self, '_pending_user_input'):
            del self._pending_user_input
        return result

    # ═══════════════════════════════════════════════════════════
    # 内部方法
    # ═══════════════════════════════════════════════════════════

    def _execute_step(self, session_id: str, step_num: int, step: Dict, previous_results: Dict = None) -> Dict:
        """执行单个步骤 — 智能路由到正确的 Agent 并构建完整任务"""
        agent_name = step.get("assigned_agent", "")
        description = step.get("description", "")
        previous_results = previous_results or {}

        # 从数据库加载详细信息
        db_step = StepDB.get(session_id, step_num)
        details = (db_step.get("details") or {}) if db_step else {}

        # 注入用户回应（continue_session 恢复执行时的上下文）
        user_response = getattr(self, '_pending_user_input', None)
        if user_response:
            details = dict(details)  # 不修改原 dict
            details["user_response"] = user_response
            details["context"] = (details.get("context", "") +
                                  f"\n[用户补充信息] {user_response}")

        executor = self._get_executor(agent_name)

        # 如果传统 Agent 不认识，尝试通过 AI Registry 路由
        if not executor:
            registry = get_registry()
            registry.scan_all()
            route = registry.route_by_goal(description)
            best_svc = route.get("service", "")
            if best_svc:
                task = {
                    "task_id": f"{session_id}_step_{step_num}",
                    "goal": description, "task_type": "shell_execute",
                    "command": "", "ai_registry_route": route,
                }
                TaskDB.save(task["task_id"], task, session_id, step_num)
                system_agent = self._agents.get("system")
                result = system_agent.run(task)
                TaskDB.update(task["task_id"], result=result, status="done")
                return {"step": step_num, "status": result.get("status", "已完成"),
                        "result": result, "agent": "ai_registry"}
            return {"step": step_num, "status": "失败", "result": f"未找到可用 Agent 处理: {description}"}

        # ── 构建任务（智能补全） ──
        # 从 Agent 的 TASK_TYPES 取第一个作为默认任务类型
        executor = self._get_executor(agent_name)
        default_task_type = executor.TASK_TYPES[0] if executor and executor.TASK_TYPES else "generic"
        task_type = default_task_type
        task = {
            "task_id": f"{session_id}_step_{step_num}",
            "goal": description,
            "task_type": task_type,
        }

        # 智能补全：根据 Agent 类型和描述自动填充必要字段
        if agent_name == "codex":
            # 如果没有 code，用 AI 生成
            if "code" not in details or not details.get("code"):
                task["目标"] = description
                task["任务类型"] = "code_execute"
            else:
                task["code"] = details["code"]
        elif agent_name == "openclaw":
            url = details.get("url", "")
            if not url:
                # 尝试从描述中提取 URL
                import re as _re
                url_match = _re.search(r'https?://[^\s]+', description)
                if url_match:
                    url = url_match.group(0)
            if url:
                task["目标URL"] = url
                task["任务类型"] = details.get("task_type", "browser_scrape")
            else:
                task["目标URL"] = description
                task["任务类型"] = "browser_scrape"
        elif agent_name == "system":
            task["命令"] = details.get("command", description)
        elif agent_name == "qa":
            # 传递上一步结果给 QA
            if previous_results:
                prev_keys = sorted(previous_results.keys())
                if prev_keys:
                    last = previous_results[prev_keys[-1]]
                    task["result"] = last.get("result", last)
                    task["extracted_data"] = last.get("data", [])
            task["goal"] = description
            task["expected_output"] = details.get("expected_output", "")

        # 合并 details 中的所有字段
        for key in ("url", "code", "files", "selector", "command", "mode", "extract",
                    "task_type", "goal", "expected_output", "context", "constraints",
                    "priority", "project_id", "目标", "目标URL", "任务类型", "命令"):
            if key in details and key not in task:
                task[key] = details[key]

        # v1.5.1: 依赖注入 — 如果此步骤声明了 depends_on_step，注入前置步骤的输出
        depends_on = details.get("depends_on_step") if isinstance(details, dict) else None
        if depends_on and previous_results and depends_on in previous_results:
            prev_output = previous_results[depends_on]
            injected_context = task.get("context", "")
            injected_context += "\n\n[前置步骤输出] " + json.dumps(prev_output, ensure_ascii=False)[:3000]
            task["context"] = injected_context
            _cmd_logger.info(f"[Commander] 步骤 {step_num} 注入了步骤 {depends_on} 的输出")

        # 保存
        TaskDB.save(task["task_id"], task, session_id, step_num)

        try:
            result = executor.run(task)
            TaskDB.update(task["task_id"], result=result, status="done")
            return {"step": step_num, "status": "已完成", "result": result, "agent": agent_name}
        except Exception as e:
            import traceback
            error = f"{str(e)[:200]}\n{traceback.format_exc()[-300:]}"
            TaskDB.update(task["task_id"], result={"error": error}, status="failed")
            return {"step": step_num, "status": "失败", "result": error, "agent": agent_name}

    def _make_decision(self, step: Dict, result: Dict, retry_count: int, remaining_steps: int = 0) -> Dict:
        """AI 决策下一步"""
        try:
            prompt = json.dumps({
                "step": step["step_number"],
                "description": step.get("description", ""),
                "result_summary": str(result.get("result", ""))[:500],
                "retry_count": retry_count,
                "remaining_steps": remaining_steps,
            }, ensure_ascii=False)
            raw = _call_ai_v2(f"【决策模式】根据执行结果决定下一步(continue/retry/adjust/ask/complete)，输出JSON:\n{prompt}", system=UNIFIED_SYSTEM_PROMPT)
            return json.loads(raw)
        except Exception:
            # 降级：默认继续
            return {"decision": "continue", "reason": "AI 决策失败，默认继续"}

    def _generate_summary(self, session_id: str, results: List[Dict], goal: str = "") -> str:
        """生成执行总结 — 用AI提炼原始数据为简洁可读的报告"""
        total = len(results)
        success = sum(1 for r in results if r.get("status") == "已完成")
        failed = total - success

        # 合并所有原始数据
        all_lines = []
        for r in results:
            if r.get("goal"):
                goal = r["goal"]
            result_data = r.get("result", {})
            if isinstance(result_data, dict):
                data = result_data.get("data", [])
                if data:
                    # 过滤菜单/导航/脚本类文本
                    filtered = [l for l in data
                                if len(l.strip()) > 30
                                and not any(x in l for x in ["menu", "cookie", "privacy", "login",
                                                              "sign up", "donate", "javascript",
                                                              "function()", "var ", "const ",
                                                              "getElementById", "addEventListener"])]
                    # 取前60行有实质内容的
                    all_lines.extend(filtered[:60])

        raw_text = "\n".join(all_lines)

        # 用 AI 总结
        if raw_text and len(raw_text) > 100:
            try:
                prompt = f"""用户目标：{goal if goal else '(未记录)'}

以下是搜索引擎抓取的原始文本，请从中提取关键信息，生成一份简洁的概览报告。
要求：
- 如果是公司列表类查询：列出公司名称 + 一句话描述，按类别分组
- 如果是竞品分析类：列出关键数据 + 对比要点
- 如果是文章摘要类：提炼3-5个核心要点
- 总长度不超过500字
- 用中文回答
- 使用 bullet point 格式，每行不超过40字
- 不要写"根据搜索结果""搜索结果显示"这类废话

原始数据：
{raw_text[:3000]}"""

                summary_text = _call_ai_v2(f"【摘要模式】提炼以下搜索结果为简洁中文摘要:\n{prompt}", system=UNIFIED_SYSTEM_PROMPT)
                # 清理 AI 可能的多余格式
                summary_text = summary_text.strip().strip("`").strip()
            except Exception as e:
                # AI 失败，降级为规则模式
                summary_text = self._rule_summarize(all_lines, goal)
        else:
            summary_text = self._rule_summarize(all_lines, goal)

        return f"✅ 执行完成：共 {total} 步，成功 {success} 步\n\n━━━ 结果概览 ━━━\n{summary_text}"

    def _rule_summarize(self, lines: List[str], goal: str) -> str:
        """规则模式降级 — 提取关键句子"""
        # 提取包含公司名、产品名、数字的行
        import re
        key_lines = []
        for line in lines:
            # 包含公司名特征的行
            if re.search(r'(公司|inc|corp|ai|AI|runway|sora|video|生成|工具|平台)', line):
                if len(line) < 150 and line not in key_lines:
                    key_lines.append(line.strip())
            if len(key_lines) >= 15:
                break
        if key_lines:
            return "关键信息摘要：\n" + "\n".join(f"• {l}" for l in key_lines)
        return "执行完成，未提取到结构化数据。请点击查看完整执行详情。"

    # ═══════════════════════════════════════════════════════════
    # 信息查询
    # ═══════════════════════════════════════════════════════════

    def get_session_status(self, session_id: str) -> Dict:
        session = SessionDB.get(session_id)
        if not session:
            return {"status": "error", "message": "Session 不存在"}
        steps = StepDB.list_by_session(session_id)
        return {
            "session": session,
            "steps": steps,
            "step_count": len(steps),
            "completed_count": sum(1 for s in steps if s["status"] == "completed"),
        }
