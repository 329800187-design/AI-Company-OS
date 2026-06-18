"""
CEO Agent - 任务拆解智能体

负责：
1. 理解用户自然语言目标
2. 智能拆解为可执行的任务列表
3. 生成标准化的任务数据，分配给执行 Agent

支持：
- AI 模式：调用大模型智能拆解
- 规则模式：无 API 时的降级方案
"""
import os
import json
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.config import get_ai_config, AI_PROVIDER
from core.agent_timing import timed


# 可分配给哪些执行 Agent
EXECUTION_AGENTS = {
    "codex_agent": {
        "role": "代码执行",
        "task_types": ["code_execute", "code_write_and_run", "code_test", "code_debug", "code_refactor"],
        "description": "执行代码、创建文件、运行测试、调试修复",
    },
    "cto_agent": {
        "role": "技术审查",
        "task_types": ["code_review", "tech_choice", "architecture_review", "task_decompose", "effort_estimate"],
        "description": "代码审查、技术选型建议、架构评审、任务拆解、工作量评估",
    },
    "image_agent": {
        "role": "图片生成",
        "task_types": ["image_generate", "image_analyze"],
        "description": "AI 图片生成（DALL-E 3）、图片分析",
    },
    "marketing_agent": {
        "role": "营销内容",
        "task_types": ["copywriting", "social_media", "seo_article", "email_campaign", "brand_strategy", "campaign_plan"],
        "description": "文案生成、社媒内容、SEO 文章、邮件营销、品牌策略、活动策划",
    },
    "video_agent": {
        "role": "视频创意",
        "task_types": ["video_script", "video_storyboard", "video_idea"],
        "description": "视频脚本、分镜脚本、创意点子生成",
    },
    "qa_agent": {
        "role": "质量验收",
        "task_types": ["qa_review", "qa_test"],
        "description": "检查任务结果是否符合预期，给出评分和建议",
    },
    "data_agent": {
        "role": "数据分析",
        "task_types": ["data_load", "data_explore", "data_clean", "data_analyze", "data_viz", "data_export"],
        "description": "加载CSV/Excel/JSON数据，探索、清洗、统计分析、可视化图表、导出",
    },
    "openclaw_agent": {
        "role": "浏览器操作",
        "task_types": ["browser_screenshot", "browser_scrape", "browser_form_fill", "browser_test"],
        "description": "打开网页、截图、抓取内容、填写表单、页面测试",
    },
    "system_agent": {
        "role": "系统操作 + 本地 AI",
        "task_types": ["shell_execute", "shell_cmd", "system_run", "run_program",
                       "file_write", "file_read", "file_list", "file_search",
                       "local_ai", "local_ai_list", "process_list", "process_kill"],
        "description": "执行命令行、启动本地程序、读写文件、调用本地 AI 模型（Ollama/llama.cpp/LM Studio）",
    },
}

# AI Registry 外部资源（不在本地 Agent 中执行，通过 AI Registry 路由）
EXTERNAL_AI_SERVICES = {
    "cc-switch": {
        "role": "AI 推理 (DeepSeek V4 Pro)",
        "task_types": ["chat", "analysis", "summary", "translate", "brainstorm", "write"],
        "description": "通过 CC Switch 代理调用 DeepSeek V4 Pro，通用推理、分析、创作",
    },
    "chatgpt": {
        "role": "通用对话 + 图片生成",
        "task_types": ["chat", "image_generate", "image_edit", "poster", "design", "write", "brainstorm"],
        "description": "OpenAI ChatGPT，通用对话 + DALL-E 图片生成",
    },
    "kimi": {
        "role": "长文档分析 + 深度阅读",
        "task_types": ["file_analyze", "long_context", "deep_read", "report", "analysis", "summary"],
        "description": "Moonshot Kimi，擅长超长文档分析、深度阅读、报告总结",
    },
}

# AI 拆解用的 System Prompt
CEO_SYSTEM_PROMPT = """你是一个技术 CEO，负责将一个用户目标拆解为多个可执行的任务。

你可以调度的 Agent：
- codex_agent: 代码执行、创建文件、运行测试、调试修复
- openclaw_agent: 浏览器操作、网页截图、内容抓取、表单填写、页面测试
- system_agent: 本地系统操作 — 执行命令行、启动本地程序、读写文件、调用本地 AI 模型（Ollama / llama.cpp / LM Studio）
- qa_agent: 质量验收、评分、问题反馈
- cto_agent: 技术审查 — 代码审查、技术选型建议、架构评审、任务拆解、工作量评估
- image_agent: 图片生成 — AI 文生图（DALL-E 3）、图片分析
- marketing_agent: 营销内容 — 文案、SEO、社媒、邮件、品牌策略、活动策划
- video_agent: 视频创意 — 视频脚本、分镜脚本、创意点子
- data_agent: 数据分析 — 加载CSV/Excel/JSON、数据探索、清洗、统计分析、可视化、导出

每个任务必须包含以下字段：
- task_type: 任务类型 (code_execute/code_write_and_run/code_test/browser_screenshot/browser_scrape/browser_form_fill/browser_test/qa_review/code_review/tech_choice/architecture_review/effort_estimate/image_generate/copywriting/social_media/seo_article/video_script/data_load/data_explore/data_analyze/data_viz/data_export)
- assigned_to: 分配给哪个 Agent (codex_agent/openclaw_agent/system_agent/qa_agent/cto_agent/image_agent/marketing_agent/video_agent/data_agent/cc-switch/chatgpt/kimi)
- priority: 优先级 (high/normal/low)
- goal: 任务目标（一句话描述）
- context: 任务上下文和背景（2-3句话）
- url: 如果是浏览器任务，提供目标 URL，否则留空 ""
- selector: 如果是浏览器任务需要定位元素，提供 CSS 选择器，否则留空 ""
- code: 如果是代码任务，提供完整代码，否则留空 ""
- files: 需要创建的文件，格式为 {"文件名": "文件内容"}，否则留空 {}
- expected_output: 期望产出，格式为 {"type": "类型", "description": "描述"}

拆解原则：
1. 涉及代码的任务分配给 codex_agent
2. 涉及网页操作的任务分配给 openclaw_agent
3. 涉及系统命令/本地文件的任务分配给 system_agent
4. 通用推理/分析/创作任务分配给 cc-switch (DeepSeek V4 Pro)
5. 长文档/多文件分析分配给 kimi
6. 图片生成分配给 chatgpt
7. qa_review 放在最后验收
8. 按逻辑顺序排列，先执行后验收
9. 通常 1-3 个任务，不要过度拆解

生成 URL 的规则：
- **不要**用 Wikipedia 精确页面名（页面名很难猜对），用 Google 搜索代替
- 搜索信息时用 Google：https://www.google.com/search?q=关键词（空格用 + 连接）
- 需要查公司官网时，直接写具体网址如 https://openai.com/sora 或 https://runwayml.com
- 对于行业调研/公司列表类任务，也可以用 https://www.google.com/search?q=top+AI+video+generation+companies+2024 这样的搜索

返回格式：只返回一个 JSON 数组，不要任何其他文字。"""


class CEOAgent(BaseAgent):
    """
    CEO Agent - 目标拆解

    默认尝试使用 AI API 拆解，如果不可用则降级为规则模式。
    """

    AGENT_ID = "ceo"
    DISPLAY_NAME = "目标拆解"
    CAPABILITIES = ["decompose", "planning"]
    TASK_TYPES = ["goal_decompose", "task_planning"]

    def __init__(self, api_key: Optional[str] = None, model: str = ""):
        super().__init__(name="ceo")
        try:
            config = get_ai_config()
            self.api_key = api_key or config["api_key"]
            self.model = model or config["model"]
            self.api_base = config["base_url"]
        except RuntimeError:
            # 降级：尝试通过 CC Switch 或默认 DeepSeek
            cc_switch = os.getenv("CC_SWITCH_URL", "")
            if cc_switch:
                self.api_key = "not-needed"
                self.model = "deepseek-v4-pro"
                self.api_base = cc_switch.rstrip("/")
            else:
                self.api_key = ""
                self.model = "deepseek-chat"
                self.api_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    @timed("ceo")
    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", "ceo_task_001")
        user_goal = task.get("goal", "").strip()

        if not user_goal:
            return self.fail(
                task_id=task_id,
                error="缺少用户目标，无法拆解任务",
                meta={"score": 0, "problems": ["用户目标为空，请提供任务描述"],
                       "next_suggestion": "请提供明确的目标描述，例如：写一个计算质数的Python脚本"},
            )

        # 尝试 AI 拆解
        if self.api_key:
            created_tasks = self._ai_decompose(user_goal)
            if created_tasks:
                return self._chinese_result(
                    task_id=task_id,
                    status="已完成",
                    summary=f"已将目标拆解为 {len(created_tasks)} 个任务（AI 智能拆解）",
                    created_tasks=created_tasks,
                    score=100,
                    problems=[],
                    next_suggestion="可将拆解结果写入任务中心并依次执行",
                )

        # 降级：规则拆解
        created_tasks = self._rule_decompose(user_goal)
        return self._chinese_result(
            task_id=task_id,
            status="已完成",
            summary=f"已将目标拆解为 {len(created_tasks)} 个任务（规则模式降级）",
            created_tasks=created_tasks,
            score=80,
            problems=["当前使用规则模式拆解，建议配置 DeepSeek API 获得更智能的拆解"],
            next_suggestion="建议配置 AI API 以获得更精准的任务拆解",
        )

    def _ai_decompose(self, goal: str) -> Optional[List[Dict[str, Any]]]:
        # 使用共享 httpx 连接池（避免每个请求新建 TCP + TLS）
        from core.http_client import get_shared_client
        client = get_shared_client()

        try:
            if AI_PROVIDER == "claude":
                resp = client.post(
                    f"{self.api_base}/messages",
                    json={
                        "model": self.model,
                        "max_tokens": 4096,
                        "system": CEO_SYSTEM_PROMPT,
                        "messages": [{"role": "user", "content": f"请将以下目标拆解为任务：{goal}"}],
                    },
                    headers={"x-api-key": self.api_key,
                             "anthropic-version": "2023-06-01"},
                    timeout=60,
                )
                resp.raise_for_status()
                content = resp.json()["content"][0]["text"]
            else:
                resp = client.post(
                    f"{self.api_base}/chat/completions",
                    json={
                        "model": self.model,
                        "messages": [
                            {"role": "system", "content": CEO_SYSTEM_PROMPT},
                            {"role": "user", "content": f"请将以下目标拆解为任务：{goal}"},
                        ],
                        "temperature": 0.7,
                        "max_tokens": 4096,
                    },
                    headers={"Authorization": f"Bearer {self.api_key}"},
                    timeout=60,
                )
                resp.raise_for_status()
                content = resp.json()["choices"][0]["message"]["content"]

            # 提取 JSON 数组
            tasks = self._extract_json_array(content)
            if not tasks:
                return None

            # 标准化每个任务
            normalized = []
            for t in tasks:
                normalized.append(self._normalize_task(t))
            return normalized

        except Exception as e:
            self.logger.warning(f"AI 拆解失败: {e}")
            return None

    def _rule_decompose(self, goal: str) -> List[Dict[str, Any]]:
        """规则模式：基于关键词匹配拆解任务"""
        goal_lower = goal.lower()
        tasks = []

        # 判断目标类型
        is_code_related = any(kw in goal_lower for kw in [
            "代码", "code", "程序", "函数", "脚本", "api", "接口",
            "python", "html", "css", "javascript", "js", "开发", "写",
            "创建", "实现", "修复", "bug", "优化", "重构",
        ])

        is_browser_related = any(kw in goal_lower for kw in [
            "网页", "页面", "网站", "浏览器", "截图", "抓取", "采集",
            "打开", "搜索", "表单", "填写", "web", "url", "http",
            "page", "screenshot", "scrape", "form", "测试页面",
        ])

        is_system_related = any(kw in goal_lower for kw in [
            "命令", "命令行", "终端", "cmd", "powershell", "bash", "shell",
            "启动", "打开程序", "运行", "执行程序", "进程", "任务管理器",
            "文件", "文件夹", "目录", "保存", "写入", "读取", "搜索文件",
            "本地ai", "本地模型", "ollama", "llama", "推理",
            "系统", "注册表", "环境变量", "安装", "卸载",
        ])

        if is_code_related and not is_browser_related and not is_system_related:
            # 代码类目标：codex 执行 + qa 验收
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "codex_agent",
                "task_type": "code_execute",
                "priority": "high",
                "goal": goal,
                "context": f"用户请求: {goal}。请编写并执行对应的代码。",
                "input": {},
                "expected_output": {
                    "type": "code_output",
                    "description": "代码执行的 stdout 输出，无错误",
                },
                "constraints": {
                    "timeout_seconds": 30,
                },
            })
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "qa_agent",
                "task_type": "qa_review",
                "priority": "normal",
                "goal": f"验收: {goal}",
                "context": f"检查上一步代码任务的执行结果是否符合预期。原目标: {goal}",
                "input": {},
                "expected_output": {
                    "type": "review_result",
                    "description": "评分 >= 70 视为通过",
                },
                "constraints": {},
            })
        elif is_browser_related:
            # 浏览器类目标：openclaw 截图/抓取 + qa 验收
            url_match = re.search(r'https?://[^\s]+', goal)
            target_url = url_match.group() if url_match else ""
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "openclaw_agent",
                "task_type": "browser_scrape",
                "priority": "high",
                "goal": goal,
                "context": f"用户请求: {goal}。请打开页面并执行浏览器操作。",
                "url": target_url,
                "input": {},
                "expected_output": {
                    "type": "browser_result",
                    "description": "返回页面内容或截图路径",
                },
                "constraints": {},
            })
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "qa_agent",
                "task_type": "qa_review",
                "priority": "normal",
                "goal": f"验收: {goal}",
                "context": f"检查浏览器操作结果是否符合预期。原目标: {goal}",
                "input": {},
                "expected_output": {
                    "type": "review_result",
                    "description": "评分 >= 70 视为通过",
                },
                "constraints": {},
            })
        elif is_system_related:
            # 系统操作类目标：system 执行 + qa 验收
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "system_agent",
                "task_type": "shell_execute",
                "priority": "high",
                "goal": goal,
                "context": f"用户请求: {goal}。请执行对应的系统操作。",
                "url": "",
                "input": {},
                "expected_output": {
                    "type": "system_result",
                    "description": "命令执行的输出或操作结果",
                },
                "constraints": {},
            })
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "qa_agent",
                "task_type": "qa_review",
                "priority": "normal",
                "goal": f"验收: {goal}",
                "context": f"检查系统操作结果是否符合预期。原目标: {goal}",
                "input": {},
                "expected_output": {
                    "type": "review_result",
                    "description": "评分 >= 70 视为通过",
                },
                "constraints": {},
            })
        else:
            # 非代码/非浏览器类目标：qa 直接评估
            tasks.append({
                "project_id": "project_001",
                "created_by": "ceo_agent",
                "assigned_to": "qa_agent",
                "task_type": "qa_review",
                "priority": "normal",
                "goal": goal,
                "context": f"用户请求: {goal}。请对此任务进行规划评估。",
                "input": {},
                "expected_output": {
                    "type": "review_result",
                    "description": "对任务做出评估和建议",
                },
                "constraints": {},
            })

        return tasks

    @staticmethod
    def _extract_json_array(text: str) -> Optional[List[Dict]]:
        """从 AI 返回文本中提取 JSON 数组"""
        # 去除 markdown 代码块
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = text.replace("```", "").strip()

        # 尝试直接解析
        try:
            result = json.loads(text)
            if isinstance(result, list):
                return result
            if isinstance(result, dict) and "tasks" in result:
                return result["tasks"]
        except json.JSONDecodeError:
            pass

        # 尝试匹配 [...] 块
        match = re.search(r"\[[\s\S]*\]", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        return None

    def _chinese_result(self, task_id, status, summary, created_tasks, score, problems, next_suggestion):
        """返回中文格式的拆解结果"""
        return self.ok(
            task_id=task_id,
            status=status,
            data={
                "summary": summary,
                "created_tasks": created_tasks,
                "task_count": len(created_tasks),
                "score": score,
                "problems": problems,
                "next_suggestion": next_suggestion,
            },
            meta={"score": score},
        )

    @staticmethod
    def _normalize_task(task: Dict[str, Any]) -> Dict[str, Any]:
        """标准化任务字段"""
        return {
            "project_id": task.get("project_id", "project_001"),
            "created_by": "ceo_agent",
            "assigned_to": task.get("assigned_to", "codex_agent"),
            "task_type": task.get("task_type", "code_execute"),
            "priority": task.get("priority", "normal"),
            "goal": task.get("goal", ""),
            "context": task.get("context", ""),
            "input": task.get("input", {}),
            "expected_output": task.get("expected_output", {"type": "code_output", "description": "执行结果"}),
            "constraints": task.get("constraints", {}),
            "code": task.get("code", ""),
            "files": task.get("files", {}),
            "url": task.get("url", ""),
            "selector": task.get("selector", ""),
        }
