"""
CTO Agent — 技术架构智能体

负责：
1. 代码审查（code review）：分析代码质量、安全问题、性能瓶颈
2. 技术选型：根据不同场景推荐合适的技术栈
3. 架构评审：评审系统设计方案、提出改进建议
4. 技术难点拆解：把复杂技术问题拆成可执行子任务
5. 工作量评估：估算开发工作量和时间

支持 AI 模式（DeepSeek/Claude）和规则降级模式。
"""
import json
import os
import re
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.config import get_ai_config, AI_PROVIDER


# AI 代码审查 System Prompt
CODE_REVIEW_PROMPT = """你是一位资深技术 CTO，负责代码审查。请分析代码并给出：

审查维度：
1. 代码质量：命名、结构、可读性
2. 安全性：SQL注入、XSS、敏感信息泄露、命令注入等
3. 性能：算法复杂度、资源使用、N+1查询等
4. 可维护性：模块化、错误处理、测试覆盖
5. 最佳实践：是否遵循语言/框架的推荐做法

输出格式（JSON）：
{
  "overall_score": 0-100,
  "summary": "一句话总结",
  "findings": [
    {"severity": "critical|high|medium|low", "category": "security|performance|quality|maintainability", "line_guess": "大致位置", "description": "问题描述", "suggestion": "修改建议"}
  ],
  "strengths": ["优点1", "优点2"],
  "improvements": ["改进建议1", "改进建议2"]
}

只输出 JSON，不要其他文字。"""

TECH_CHOICE_PROMPT = """你是一位资深技术 CTO，负责技术选型建议。根据用户的需求场景，推荐合适的技术栈。

考虑维度：
1. 场景匹配度
2. 团队学习成本
3. 性能/规模需求
4. 社区活跃度与生态
5. 长期维护成本

输出格式（JSON）：
{
  "recommendation": "首选方案名称",
  "alternatives": ["备选1", "备选2"],
  "tech_stack": {
    "语言/运行时": "推荐",
    "框架": "推荐",
    "数据库": "推荐",
    "部署": "推荐",
    "其他工具": "推荐"
  },
  "pros": ["优势1", "优势2"],
  "cons": ["劣势1", "劣势2"],
  "learning_curve": "low|medium|high",
  "suitable_scale": "small|medium|large|enterprise",
  "summary": "200字以内的选型理由"
}

只输出 JSON，不要其他文字。"""

ARCHITECT_REVIEW_PROMPT = """你是一位资深技术 CTO，负责评审系统架构设计。请分析架构并给出意见。

评审维度：
1. 架构合理性：分层是否清晰、关注点是否分离
2. 可扩展性：是否便于横向扩展、插件化程度
3. 可靠性：容错机制、故障恢复、数据一致性
4. 技术债务风险：过时技术、过度设计、耦合度过高
5. 安全性：认证授权、数据保护、攻击面

输出格式（JSON）：
{
  "overall_score": 0-100,
  "summary": "一句话总结",
  "risks": [
    {"severity": "critical|high|medium|low", "area": "可扩展性|可靠性|安全性|性能|技术债务", "description": "风险描述", "mitigation": "缓解措施"}
  ],
  "strengths": ["架构优点1", "优点2"],
  "improvement_areas": ["需要改进的方面"],
  "recommended_actions": [{"action": "具体行动", "priority": "high|medium|low", "effort": "预估工作量"}]
}

只输出 JSON，不要其他文字。"""


class CTOAgent(BaseAgent):
    """CTO Agent — 技术架构审查与决策"""

    AGENT_ID = "cto"
    DISPLAY_NAME = "技术审查"
    CAPABILITIES = ["code_review", "architecture", "tech_choice"]
    TASK_TYPES = ["code_review", "tech_choice", "architecture_review", "task_decompose", "effort_estimate"]

    def __init__(self, api_key: Optional[str] = None, model: str = "", timeout: int = 60):
        super().__init__(name="cto", timeout=timeout)
        try:
            config = get_ai_config()
            self.api_key = api_key or config["api_key"]
            self.model = model or config["model"]
            self.api_base = config["base_url"]
        except RuntimeError:
            self.api_key = ""
            self.model = "deepseek-chat"
            self.api_base = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"cto_{os.urandom(4).hex()}")
        task_type = task.get("task_type", "code_review")
        goal = task.get("goal", "")

        if not goal:
            return self._result(task_id, "失败", "请提供技术目标或需要审查的内容", score=0)

        handlers = {
            "code_review": self._handle_code_review,
            "tech_choice": self._handle_tech_choice,
            "architecture_review": self._handle_architect_review,
            "task_decompose": self._handle_task_decompose,
            "effort_estimate": self._handle_effort_estimate,
        }
        handler = handlers.get(task_type, self._handle_smart)
        return handler(task, task_id, goal)

    # ── 处理函数 ──────────────────────────────────────────

    def _handle_code_review(self, task: Dict, task_id: str, goal: str) -> Dict:
        code = task.get("code", task.get("代码", ""))
        language = task.get("language", task.get("语言", task.get("lang", "")))
        context = task.get("context", task.get("上下文", ""))

        if not code:
            return self._result(task_id, "跳过", "未提供需要审查的代码", score=0,
                               suggestions=["请提供 code 字段，包含需要审查的源代码"])

        if self.api_key:
            prompt = f"""请审查以下代码：

语言：{language or '自动检测'}
上下文：{context or '无额外上下文'}

代码：
```{language or ''}
{code[:8000]}
```"""
            ai_result = self._call_ai(CODE_REVIEW_PROMPT, prompt)
            if ai_result:
                return self._result(
                    task_id, "审查完成",
                    f"代码审查评分: {ai_result.get('overall_score', 'N/A')}/100",
                    score=ai_result.get("overall_score", 70),
                    data=ai_result,
                    suggestions=ai_result.get("improvements", []),
                    problems=ai_result.get("findings", []),
                )

        # 规则降级：基于静态检查
        findings = self._static_code_check(code, language)
        score = max(30, 100 - len(findings) * 10)
        return self._result(
            task_id, "审查完成（规则模式）",
            f"静态检查发现 {len(findings)} 个潜在问题",
            score=score,
            data={"findings": findings, "mode": "static_analysis"},
            problems=findings,
            suggestions=["建议配置 AI API Key 获得更深入的智能审查"],
        )

    def _handle_tech_choice(self, task: Dict, task_id: str, goal: str) -> Dict:
        constraints = task.get("constraints", task.get("约束", {}))
        budget = task.get("budget", task.get("预算", ""))

        if self.api_key:
            prompt = f"""需求场景：{goal}
约束条件：{json.dumps(constraints, ensure_ascii=False) if constraints else '无特殊约束'}
预算限制：{budget or '未指定'}"""
            ai_result = self._call_ai(TECH_CHOICE_PROMPT, prompt)
            if ai_result:
                return self._result(
                    task_id, "选型完成",
                    f"推荐方案: {ai_result.get('recommendation', 'N/A')}",
                    score=85,
                    data=ai_result,
                    suggestions=ai_result.get("alternatives", []),
                )

        # 规则降级
        return self._rule_tech_choice(task_id, goal, constraints)

    def _handle_architect_review(self, task: Dict, task_id: str, goal: str) -> Dict:
        arch_desc = task.get("architecture_desc", task.get("架构描述", task.get("description", goal)))
        diagram = task.get("diagram", task.get("架构图", ""))

        if self.api_key:
            prompt = f"""请评审以下系统架构：

架构描述：{arch_desc[:5000]}
{f'架构图/图描述：{diagram[:2000]}' if diagram else ''}"""
            ai_result = self._call_ai(ARCHITECT_REVIEW_PROMPT, prompt)
            if ai_result:
                return self._result(
                    task_id, "评审完成",
                    f"架构评分: {ai_result.get('overall_score', 'N/A')}/100",
                    score=ai_result.get("overall_score", 70),
                    data=ai_result,
                    problems=ai_result.get("risks", []),
                    suggestions=ai_result.get("improvement_areas", []),
                )

        # 规则降级
        return self._rule_architect_review(task_id, arch_desc)

    def _handle_task_decompose(self, task: Dict, task_id: str, goal: str) -> Dict:
        """把技术问题拆成可执行子任务"""
        if self.api_key:
            prompt = f"请将以下技术目标拆解为可执行的子任务：{goal}"
            system = """你是技术 CTO。请将技术目标拆解为子任务。
输出 JSON: {"subtasks": [{"title": "子任务", "description": "描述", "estimated_hours": 0, "dependencies": [], "skills_required": ["Python", "Docker"]}]}
只输出 JSON。"""
            ai_result = self._call_ai(system, prompt)
            if ai_result:
                subtasks = ai_result.get("subtasks", [])
                return self._result(
                    task_id, "拆解完成",
                    f"拆解为 {len(subtasks)} 个子任务",
                    score=85,
                    data={"subtasks": subtasks},
                )

        # 规则降级
        return self._result(
            task_id, "拆解完成（规则模式）",
            f"已对目标进行初步拆解",
            score=70,
            data={"subtasks": [
                {"title": "需求分析", "description": goal, "estimated_hours": 2, "dependencies": []},
                {"title": "方案设计", "description": f"设计{goal[:30]}的技术方案", "estimated_hours": 4, "dependencies": ["需求分析"]},
                {"title": "核心实现", "description": "编写核心逻辑代码", "estimated_hours": 8, "dependencies": ["方案设计"]},
                {"title": "测试验证", "description": "编写测试并验证功能", "estimated_hours": 4, "dependencies": ["核心实现"]},
            ]},
        )

    def _handle_effort_estimate(self, task: Dict, task_id: str, goal: str) -> Dict:
        """工作量评估"""
        if self.api_key:
            prompt = f"请评估以下开发任务的工作量：{goal}"
            system = """你是技术 CTO。请估算开发工作量。
输出 JSON: {"total_hours": 0, "breakdown": [{"phase": "阶段", "hours": 0, "description": "说明"}], "team_size": "建议团队人数", "risks": ["风险点"], "confidence": "low|medium|high"}
只输出 JSON。"""
            ai_result = self._call_ai(system, prompt)
            if ai_result:
                return self._result(
                    task_id, "评估完成",
                    f"预估工作量: {ai_result.get('total_hours', 'N/A')} 小时",
                    score=80,
                    data=ai_result,
                )

        # 规则降级
        return self._result(
            task_id, "评估完成（规则模式）",
            "基于经验的工作量粗略估算",
            score=65,
            data={
                "total_hours": 24,
                "breakdown": [
                    {"phase": "分析设计", "hours": 4, "description": "需求分析与技术方案"},
                    {"phase": "开发实现", "hours": 12, "description": "核心功能开发"},
                    {"phase": "测试", "hours": 4, "description": "单元测试与集成测试"},
                    {"phase": "文档部署", "hours": 4, "description": "文档与部署"},
                ],
                "team_size": "1-2人",
                "risks": ["需求变更导致返工"],
                "confidence": "low",
            },
        )

    def _handle_smart(self, task: Dict, task_id: str, goal: str) -> Dict:
        """智能推断任务类型"""
        goal_lower = goal.lower()
        code = task.get("code", task.get("代码", ""))

        if code or any(kw in goal_lower for kw in ["代码", "code", "审查", "review", "bug", "安全", "漏洞"]):
            return self._handle_code_review(task, task_id, goal)
        if any(kw in goal_lower for kw in ["架构", "设计", "方案", "architecture", "design"]):
            return self._handle_architect_review(task, task_id, goal)
        if any(kw in goal_lower for kw in ["选型", "技术栈", "推荐", "选择", "对比"]):
            return self._handle_tech_choice(task, task_id, goal)
        if any(kw in goal_lower for kw in ["拆解", "分解", "步骤", "计划", "子任务"]):
            return self._handle_task_decompose(task, task_id, goal)
        if any(kw in goal_lower for kw in ["时间", "工期", "工作量", "估算", "人天", "排期"]):
            return self._handle_effort_estimate(task, task_id, goal)

        # 默认：代码审查
        return self._handle_code_review(task, task_id, goal)

    # ── AI 调用 ──────────────────────────────────────────

    def _call_ai(self, system_prompt: str, user_prompt: str) -> Optional[Dict]:
        """调用 AI API 并解析 JSON 返回"""
        try:
            import urllib.request

            if AI_PROVIDER == "claude":
                payload = json.dumps({
                    "model": self.model,
                    "max_tokens": 4096,
                    "system": system_prompt,
                    "messages": [{"role": "user", "content": user_prompt}],
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base}/v1/messages",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "x-api-key": self.api_key,
                        "anthropic-version": "2023-06-01",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    content = body["content"][0]["text"]
            else:
                payload = json.dumps({
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.3,
                    "max_tokens": 4096,
                }).encode("utf-8")
                req = urllib.request.Request(
                    f"{self.api_base}/chat/completions",
                    data=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {self.api_key}",
                    },
                )
                with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                    body = json.loads(resp.read().decode("utf-8"))
                    content = body["choices"][0]["message"]["content"]

            return self._extract_json(content)
        except Exception as e:
            print(f"[CTO Agent] AI 调用失败: {e}")
            return None

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """从 AI 返回文本中提取 JSON 对象"""
        text = re.sub(r"```(?:json)?\s*", "", text)
        text = text.replace("```", "").strip()

        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass

        # 尝试匹配 {...} 块
        match = re.search(r"\{[\s\S]*\}", text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
        return None

    # ── 规则模式降级 ─────────────────────────────────────

    def _static_code_check(self, code: str, language: str = "") -> List[Dict]:
        """静态代码检查（规则模式）"""
        findings = []
        code_lower = code.lower()

        # Python 检查
        if language == "python" or ".py" in code[:50] or "import " in code or "def " in code:
            if "print(" in code and len(code) > 500:
                findings.append({
                    "severity": "low", "category": "quality",
                    "description": "生产代码中使用了 print()，建议用 logging",
                    "suggestion": "替换为 logging.getLogger(__name__).info()"
                })
            if "except:" in code_lower and "except Exception" not in code_lower and "except :" not in code:
                findings.append({
                    "severity": "medium", "category": "quality",
                    "description": "裸露的 except: 可能吞掉重要异常",
                    "suggestion": "明确指定异常类型，如 except ValueError:"
                })
            if "eval(" in code_lower:
                findings.append({
                    "severity": "critical", "category": "security",
                    "description": "使用了 eval()，存在代码注入风险",
                    "suggestion": "使用 ast.literal_eval() 或避免动态执行"
                })
            if "password" in code_lower or "secret" in code_lower or "api_key" in code_lower:
                if "=" in code and ('"' in code or "'" in code):
                    findings.append({
                        "severity": "high", "category": "security",
                        "description": "可能存在硬编码的敏感信息",
                        "suggestion": "使用环境变量或配置管理存储敏感信息"
                    })
            if "sql" in code_lower and ("+" in code or "%" in code or "format" in code_lower):
                findings.append({
                    "severity": "high", "category": "security",
                    "description": "疑似字符串拼接构造 SQL，存在注入风险",
                    "suggestion": "使用参数化查询 (cursor.execute(sql, params))"
                })

        # 通用检查
        if len(code) > 2000:
            findings.append({
                "severity": "medium", "category": "maintainability",
                "description": f"代码较长 ({len(code)} 字符)，建议拆分模块",
                "suggestion": "按职责拆分为多个函数/模块"
            })
        if "TODO" in code or "FIXME" in code or "HACK" in code:
            findings.append({
                "severity": "low", "category": "quality",
                "description": "存在 TODO/FIXME/HACK 标记",
                "suggestion": "在发布前处理这些标记"
            })

        return findings

    def _rule_tech_choice(self, task_id: str, goal: str, constraints: Dict) -> Dict:
        """规则模式技术选型"""
        goal_lower = goal.lower()

        if any(kw in goal_lower for kw in ["web", "网站", "后端", "api"]):
            return self._result(task_id, "选型完成（规则模式）",
                "推荐 FastAPI + SQLite/PostgreSQL 方案",
                score=75,
                data={
                    "recommendation": "FastAPI + SQLite",
                    "tech_stack": {"语言": "Python 3.12", "框架": "FastAPI", "数据库": "SQLite→PostgreSQL", "部署": "Docker"},
                    "learning_curve": "low",
                    "suitable_scale": "medium",
                },
                suggestions=["FastAPI + SQLAlchemy", "Django + DRF", "Express + Prisma"],
            )

        if any(kw in goal_lower for kw in ["前端", "frontend", "ui", "页面", "react", "vue"]):
            return self._result(task_id, "选型完成（规则模式）",
                "推荐 React/Next.js + TypeScript 方案",
                score=75,
                data={
                    "recommendation": "Next.js + TypeScript",
                    "tech_stack": {"语言": "TypeScript", "框架": "Next.js", "UI": "Tailwind CSS", "部署": "Vercel/Docker"},
                    "learning_curve": "medium",
                    "suitable_scale": "medium",
                },
                suggestions=["React + Vite", "Vue 3 + Nuxt", "SvelteKit"],
            )

        if any(kw in goal_lower for kw in ["数据", "data", "分析", "ai", "ml", "机器学习"]):
            return self._result(task_id, "选型完成（规则模式）",
                "推荐 Python + Jupyter + FastAPI 方案",
                score=75,
                data={
                    "recommendation": "Python 数据分析栈",
                    "tech_stack": {"语言": "Python", "框架": "FastAPI", "分析": "pandas + matplotlib", "AI": "访问外部 LLM API"},
                    "learning_curve": "low",
                    "suitable_scale": "small",
                },
            )

        return self._result(task_id, "选型完成（规则模式）",
            "推荐 Python + FastAPI 通用方案",
            score=70,
            data={"recommendation": "Python + FastAPI 通用方案"},
            suggestions=["建议在 Web UI 配置 AI API Key 获得更精准的选型建议"],
        )

    def _rule_architect_review(self, task_id: str, arch_desc: str) -> Dict:
        """规则模式架构评审"""
        findings = []
        arch_lower = arch_desc.lower()

        if "单点" in arch_lower or "single" in arch_lower:
            findings.append({
                "severity": "high", "area": "可靠性",
                "description": "存在单点故障风险",
                "mitigation": "引入冗余/负载均衡"
            })
        if "同步" in arch_lower and "异步" not in arch_lower:
            findings.append({
                "severity": "medium", "area": "性能",
                "description": "全同步架构可能影响吞吐量",
                "mitigation": "引入消息队列异步处理耗时操作"
            })

        score = max(40, 80 - len(findings) * 15)
        return self._result(
            task_id, "评审完成（规则模式）",
            f"架构评审完成，发现 {len(findings)} 个潜在问题",
            score=score,
            data={"findings": findings, "mode": "rule_based"},
            problems=findings,
            suggestions=["建议在 Web UI 配置 AI API Key 获得更深入的智能评审"],
        )

    # ── 结果构建 ──────────────────────────────────────────

    def _result(self, task_id: str, status: str, summary: str, score: int = 70,
                data: Dict = None, problems: List = None, suggestions: List = None) -> Dict:
        """标准化结果"""
        return self.ok(
            task_id=task_id,
            status=status,
            data={
                "summary": summary,
                "score": score,
                "data": data or {},
                "findings": problems or [],
                "suggestions": suggestions or [],
            },
            meta={"score": score},
        )
